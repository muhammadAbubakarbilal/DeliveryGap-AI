"""Freeze reviewed scope/evidence in one project-locked transaction; render only the snapshot."""

import csv
import io
import json
import re

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.analysis_models import AnalysisRun, Finding
from app.evidence_models import ArtifactLink, ArtifactRevision, DeliveryArtifact
from app.models import Project, now
from app.operation_models import Operation, ReportSnapshot
from app.operation_schemas import OverviewOut, ReportCreate
from app.requirement_models import Baseline, BaselineItem, RequirementVersion


def freeze(
    db: Session,
    project_id: str,
    baseline_id: str,
    filters: ReportCreate | None = None,
) -> dict[str, object]:
    baseline = db.scalar(
        select(Baseline).where(Baseline.id == baseline_id, Baseline.project_id == project_id)
    )
    if baseline is None:
        raise HTTPException(404, "Baseline not found")
    requirements: list[dict[str, object]] = []
    items = list(
        db.execute(
            select(BaselineItem, RequirementVersion)
            .join(RequirementVersion, RequirementVersion.id == BaselineItem.requirement_version_id)
            .where(BaselineItem.baseline_id == baseline_id)
            .order_by(BaselineItem.requirement_code)
        )
    )
    if len(items) > 1000:
        raise HTTPException(413, "Baseline exceeds the report limit of 1000 requirements")
    links_by_requirement: dict[str, list[dict[str, object]]] = {}
    link_rows = list(
        db.execute(
            select(ArtifactLink, DeliveryArtifact, ArtifactRevision)
            .join(DeliveryArtifact, DeliveryArtifact.id == ArtifactLink.artifact_id)
            .outerjoin(
                ArtifactRevision,
                and_(
                    ArtifactRevision.artifact_id == ArtifactLink.artifact_id,
                    ArtifactRevision.revision == ArtifactLink.artifact_revision,
                ),
            )
            .where(
                ArtifactLink.project_id == project_id,
                ArtifactLink.requirement_version_id.in_([v.id for _, v in items]),
            )
            .limit(10001)
        )
    )
    if len(link_rows) > 10000:
        raise HTTPException(413, "Report exceeds 10000 evidence links")
    for link, artifact, inspected in link_rows:
        links_by_requirement.setdefault(link.requirement_version_id, []).append(
            {
                "id": link.id,
                "review_status": link.review_status,
                "reviewed_by": link.reviewed_by,
                "revision": link.revision,
                "artifact_revision": link.artifact_revision,
                "current_artifact_revision": artifact.revision,
                "stale": link.artifact_revision != artifact.revision,
                "artifact": inspected.snapshot if inspected else None,
            }
        )
    for item, version in items:
        requirements.append(
            {
                "code": item.requirement_code,
                "version_id": version.id,
                "title": version.title,
                "content": version.content,
                "source_version_id": version.source_version_id,
                "source_span_id": version.source_span_id,
                "source_quote": version.source_quote,
                "links": links_by_requirement.get(version.id, []),
            }
        )
    finding_query = (
        select(Finding, AnalysisRun)
        .join(AnalysisRun, Finding.run_id == AnalysisRun.id)
        .where(Finding.project_id == project_id, AnalysisRun.baseline_id == baseline_id)
    )
    if filters is not None and filters.run_ids is not None:
        finding_query = finding_query.where(AnalysisRun.id.in_(filters.run_ids))
    if filters is not None and filters.classifications:
        finding_query = finding_query.where(Finding.classification.in_(filters.classifications))
    if filters is not None and filters.review_statuses:
        finding_query = finding_query.where(Finding.review_status.in_(filters.review_statuses))
    findings = [
        {
            "id": finding.id,
            "run_id": run.id,
            "provider": run.provider,
            "classification": finding.classification,
            "summary": finding.summary,
            "requirement_version_id": finding.requirement_version_id,
            "evidence_quote": finding.evidence_quote,
            "input_quote": finding.input_quote,
            "request_index": finding.request_index,
            "input_span_start": finding.input_span_start,
            "input_span_end": finding.input_span_end,
            "review_status": finding.review_status,
            "revision": finding.revision,
        }
        for finding, run in db.execute(finding_query.order_by(Finding.id).limit(10001))
    ]
    if len(findings) > 10000:
        raise HTTPException(413, "Report exceeds 10000 findings")
    return {
        "schema_version": 1,
        "project_id": project_id,
        "project_name": db.get_one(Project, project_id).name,
        "baseline_id": baseline_id,
        "baseline_number": baseline.number,
        "generated_at": now().isoformat(),
        "filters": (
            {
                "run_ids": filters.run_ids,
                "classifications": filters.classifications,
                "review_statuses": filters.review_statuses,
            }
            if filters is not None
            else {"run_ids": None, "classifications": [], "review_statuses": []}
        ),
        "requirements": requirements,
        "findings": findings,
        "limitations": "Findings are proposals. "
        "Missing evidence is not proof of missing implementation. "
        "Repeated analysis runs are listed separately, not counted as distinct approved changes.",
    }


def overview(payload: dict[str, object]) -> OverviewOut:
    # Snapshot structure is internally generated; the public API never accepts it as input.
    rows = payload["requirements"]
    assert isinstance(rows, list)
    covered = sum(
        any(link["review_status"] == "accepted" and not link["stale"] for link in r["links"])
        for r in rows
    )
    findings = payload["findings"]
    assert isinstance(findings, list)
    return OverviewOut(
        baseline_id=str(payload["baseline_id"]),
        requirements=len(rows),
        accepted_current_evidence=covered,
        missing_current_evidence=len(rows) - covered,
        stale_links=sum(link["stale"] for r in rows for link in r["links"]),
        pending_findings=sum(f["review_status"] == "pending" for f in findings),
    )


def create_snapshot(db: Session, operation: Operation) -> dict[str, object]:
    filters = ReportCreate.model_validate(operation.payload)
    snapshot = ReportSnapshot(
        project_id=operation.project_id,
        operation_id=operation.id,
        payload=freeze(db, operation.project_id, filters.baseline_id, filters),
    )
    db.add(snapshot)
    db.flush()
    return {"report_id": snapshot.id, "overview": overview(snapshot.payload).model_dump()}


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n"))
        else text
    )


def markdown(value: object) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+.!|<>~-])", r"\\\1", str(value or ""))


def render(payload: dict[str, object], format: str) -> str:
    rows, findings = payload["requirements"], payload["findings"]
    assert isinstance(rows, list) and isinstance(findings, list)
    if format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            ["record_type", "baseline_id", "generated_at", "id", "text", "state", "evidence"]
        )
        for row in rows:
            writer.writerow(
                [
                    safe_cell(v)
                    for v in [
                        "requirement",
                        payload["baseline_id"],
                        payload["generated_at"],
                        row["code"],
                        row["content"],
                        "approved",
                        json.dumps(row, ensure_ascii=False),
                    ]
                ]
            )
        for finding in findings:
            writer.writerow(
                [
                    safe_cell(v)
                    for v in [
                        "finding",
                        payload["baseline_id"],
                        payload["generated_at"],
                        finding["id"],
                        finding["summary"],
                        finding["review_status"],
                        json.dumps(finding, ensure_ascii=False),
                    ]
                ]
            )
        return output.getvalue()
    lines = [
        "# DeliveryGap review report",
        "",
        markdown(payload["project_name"]),
        f"Baseline: {payload['baseline_id']}",
        f"Generated: {payload['generated_at']}",
        "",
        "Filters: " + json.dumps(payload.get("filters", {}), ensure_ascii=False),
        "",
        str(payload["limitations"]),
        "",
        "## Approved scope",
    ]
    for row in rows:
        lines += [
            f"### {markdown(row['code'])}: {markdown(row['title'])}",
            markdown(row["content"]),
            "Source excerpt: " + markdown(row["source_quote"]),
        ]
        if row["source_version_id"] and row["source_span_id"]:
            lines += [f"Source version: {row['source_version_id']}; span: {row['source_span_id']}"]
        for link in row["links"]:
            artifact = link["artifact"] or {}
            lines += [
                f"- {markdown(artifact.get('title', 'Unknown inspected revision'))}: "
                f"{link['review_status']}; artifact revision {link['artifact_revision']}; "
                f"stale: {link['stale']}"
            ]
    lines += ["", "## Finding proposals and decisions"]
    for finding in findings:
        lines += [
            f"- {finding['classification']} / {finding['review_status']}: "
            f"{markdown(finding['summary'])}",
            f"  Run: {finding['run_id']}; provider: {markdown(finding['provider'])}",
            "  Request excerpt: " + markdown(finding["input_quote"]),
            (
                f"  Request span: [{finding['input_span_start']},"
                f"{finding['input_span_end']}) Unicode code points"
                if finding["input_span_start"] is not None and finding["input_span_end"] is not None
                else "  Request span: unavailable"
            ),
            "  Citation: " + markdown(finding["evidence_quote"]),
        ]
    return "\n\n".join(lines) + "\n"
