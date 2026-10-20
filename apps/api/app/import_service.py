"""Bounded CSV preview and transactionally committed, revision-preserving imports."""

import csv
import hashlib
import io
from datetime import UTC, datetime

from fastapi import HTTPException
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands import lock_write, remember, replay
from app.evidence_models import ArtifactLink, ArtifactRevision, DeliveryArtifact
from app.evidence_schemas import ArtifactCreate, ArtifactOut
from app.models import now
from app.operation_models import Operation
from app.operation_schemas import ImportPreview, PreviewOut, PreviewRow
from app.requirement_models import Baseline, BaselineItem
from app.security import Principal, audit


def preview(
    db: Session, auth: Principal, project_id: str, body: ImportPreview, key: str
) -> PreviewOut:
    lock_write(db, auth, project_id)
    previous = replay(db, auth, project_id, "import.preview", key, body)
    if previous is not None:
        return PreviewOut.model_validate(previous)
    if len(body.csv_text.encode("utf-8")) > 1_000_000:
        raise HTTPException(413, "CSV exceeds 1 MB")
    references: dict[str, str] = {}
    if body.baseline_id:
        baseline = db.scalar(
            select(Baseline).where(
                Baseline.id == body.baseline_id, Baseline.project_id == project_id
            )
        )
        if baseline is None:
            raise HTTPException(404, "Baseline not found")
        references = {
            item.requirement_code: item.requirement_version_id
            for item in db.scalars(
                select(BaselineItem).where(BaselineItem.baseline_id == baseline.id)
            )
        }
    reader = csv.DictReader(io.StringIO(body.csv_text.lstrip("\ufeff")), strict=True)
    required = (
        {"external_id", "title", "description", "status"}
        if body.kind == "task"
        else {"test_id", "name", "result", "executed_at"}
    )
    allowed = required | {"url", "updated_at", "requirement_id", "related_requirement_id"}
    if body.kind == "test":
        allowed |= {"environment"}
    try:
        headers = reader.fieldnames or []
        mapping = body.column_mapping
        if (
            set(mapping) - allowed
            or any(not value or value not in headers for value in mapping.values())
            or len(set(mapping.values())) != len(mapping)
        ):
            raise HTTPException(
                422, "Column mapping has unsupported fields, missing headers, or reused columns"
            )
        reverse = {source: target for target, source in mapping.items()}
        normalized_headers = [reverse.get(header, header) for header in headers]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise HTTPException(422, "Column mapping produces duplicate destination fields")
        reader.fieldnames = normalized_headers
        headers = normalized_headers
        if len(headers) != len(set(headers)) or not required.issubset(headers):
            raise HTTPException(422, "CSV headers are missing or duplicated")
        if set(headers) - allowed:
            raise HTTPException(422, "CSV has unsupported columns; use the documented template")
        rows: list[PreviewRow] = []
        seen: dict[str, PreviewRow] = {}
        existing = {
            a.external_id: a
            for a in db.scalars(
                select(DeliveryArtifact).where(
                    DeliveryArtifact.project_id == project_id,
                    DeliveryArtifact.provider == "csv",
                    DeliveryArtifact.kind == body.kind,
                )
            )
        }
        for number, raw in enumerate(reader, 2):
            if len(rows) >= 500:
                raise HTTPException(413, "CSV exceeds 500 rows")
            row = PreviewRow(number=number)
            rows.append(row)
            if None in raw or any(value is None for value in raw.values()):
                row.errors.append("Column count does not match the header")
                continue
            values = {k: v.strip() for k, v in raw.items()}
            external_id = values.get("external_id", values.get("test_id", ""))
            if external_id in seen:
                row.errors.append("Duplicate identifier in this CSV")
                seen[external_id].errors.append("Duplicate identifier in this CSV")
            seen[external_id] = row
            timestamp = (
                values.get("executed_at") if body.kind == "test" else values.get("updated_at")
            )
            parsed_time: datetime | None = None
            if body.kind == "test" or timestamp:
                try:
                    parsed = datetime.fromisoformat(timestamp or "")
                    if parsed.tzinfo is None or parsed.utcoffset() is None:
                        raise ValueError
                    parsed_time = parsed.astimezone(UTC)
                except ValueError:
                    row.errors.append("Execution/update timestamp must include a timezone")
            reference = values.get("requirement_id") or values.get("related_requirement_id")
            if (
                values.get("requirement_id")
                and values.get("related_requirement_id")
                and values["requirement_id"] != values["related_requirement_id"]
            ):
                row.errors.append("Requirement aliases disagree")
            if reference:
                row.requirement_version_id = references.get(reference)
                if row.requirement_version_id is None:
                    row.errors.append("Requirement code is not in the selected published baseline")
            status = values.get("status", values.get("result", "")).lower().replace(" ", "_")
            status = {"passed": "pass", "failed": "fail", "in-progress": "in_progress"}.get(
                status, status
            )
            valid = (
                {"pass", "fail", "skipped", "blocked", "not_run"}
                if body.kind == "test"
                else {"todo", "open", "in_progress", "done", "closed", "blocked", "cancelled"}
            )
            if status not in valid:
                row.errors.append("Unsupported status/result")
            try:
                artifact = ArtifactCreate(
                    kind=body.kind,
                    external_id=external_id,
                    title=values.get("title", values.get("name", "")),
                    status=status,
                    description=(values.get("description", "")),
                    url=HttpUrl(values["url"]) if values.get("url") else None,
                    executed_at=parsed_time if body.kind == "test" else None,
                    environment=(
                        values.get("environment") or None if body.kind == "test" else None
                    ),
                )
                row.artifact = artifact.model_dump(mode="json", exclude={"expected_revision"})
                row.expected_revision = (
                    existing[external_id].revision if external_id in existing else None
                )
            except ValidationError:
                row.errors.append("Invalid identifier, title, description, or HTTP(S) URL")
    except csv.Error as exc:
        raise HTTPException(422, "Malformed CSV") from exc
    if not rows:
        raise HTTPException(422, "CSV contains no data rows")
    operation = Operation(
        project_id=project_id,
        actor_id=auth.user.id,
        kind="import",
        payload={
            "rows": [r.model_dump(mode="json") for r in rows],
            "kind": body.kind,
            "baseline_id": body.baseline_id,
            "sha256": hashlib.sha256(body.csv_text.encode()).hexdigest(),
            "column_mapping": body.column_mapping,
        },
    )
    db.add(operation)
    db.flush()
    result = PreviewOut.model_validate({**operation_view(operation), "rows": rows})
    remember(db, auth, project_id, "import.preview", key, body, result)
    audit(db, auth.user, "import.previewed", operation.id, project_id)
    db.commit()
    return result


def operation_view(operation: Operation) -> dict[str, object]:
    from app.operation_schemas import OperationOut

    return OperationOut.model_validate(operation).model_dump()


def apply_import(db: Session, operation: Operation) -> dict[str, object]:
    rows = TypeAdapter(list[PreviewRow]).validate_python(operation.payload["rows"])
    accepted = changed = unchanged = 0
    for row in rows:
        if row.errors or row.artifact is None:
            continue
        parsed_artifact = ArtifactCreate.model_validate(row.artifact)
        values = parsed_artifact.model_dump(exclude={"expected_revision"})
        values["url"] = str(parsed_artifact.url) if parsed_artifact.url else None
        artifact = db.scalar(
            select(DeliveryArtifact).where(
                DeliveryArtifact.project_id == operation.project_id,
                DeliveryArtifact.provider == "csv",
                DeliveryArtifact.kind == values["kind"],
                DeliveryArtifact.external_id == values["external_id"],
            )
        )
        actual_revision = artifact.revision if artifact else None
        if actual_revision != row.expected_revision:
            raise HTTPException(409, "Artifacts changed after preview; preview this CSV again")
        same = artifact is not None and all(
            _same_artifact_value(getattr(artifact, field), value) for field, value in values.items()
        )
        if same:
            unchanged += 1
        else:
            if artifact is None:
                artifact = DeliveryArtifact(
                    project_id=operation.project_id, provider="csv", **values
                )
                db.add(artifact)
            else:
                for field, value in values.items():
                    setattr(artifact, field, value)
                artifact.revision += 1
                artifact.updated_at = now()
            db.flush()
            db.add(
                ArtifactRevision(
                    artifact_id=artifact.id,
                    revision=artifact.revision,
                    project_id=operation.project_id,
                    actor_id=operation.actor_id,
                    snapshot=ArtifactOut.model_validate(artifact).model_dump(mode="json"),
                )
            )
            changed += 1
        assert artifact is not None
        if row.requirement_version_id:
            exists = db.scalar(
                select(ArtifactLink.id).where(
                    ArtifactLink.project_id == operation.project_id,
                    ArtifactLink.artifact_id == artifact.id,
                    ArtifactLink.requirement_version_id == row.requirement_version_id,
                )
            )
            if exists is None:
                db.add(
                    ArtifactLink(
                        project_id=operation.project_id,
                        artifact_id=artifact.id,
                        requirement_version_id=row.requirement_version_id,
                        origin="csv",
                        artifact_revision=artifact.revision,
                        review_status="proposed",
                    )
                )
        accepted += 1
    return {
        "accepted": accepted,
        "rejected": len(rows) - accepted,
        "changed": changed,
        "unchanged": unchanged,
    }


def _same_artifact_value(current: object, expected: object) -> bool:
    if isinstance(current, datetime) and isinstance(expected, datetime):
        current_utc = (
            current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)
        )
        return current_utc == expected.astimezone(UTC)
    return current == expected
