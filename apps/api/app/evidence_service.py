from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands import lock_write, remember, replay
from app.evidence_models import ArtifactLink, ArtifactRevision, DeliveryArtifact, LinkDecision
from app.evidence_schemas import (
    ArtifactCreate,
    ArtifactOut,
    BulkLinkReview,
    BulkLinkReviewOut,
    LinkCreate,
    LinkOut,
    LinkReview,
    TraceabilityOut,
)
from app.requirement_models import Baseline, BaselineItem
from app.security import Principal, audit, project_access


def create_artifact(
    project_id: str, body: ArtifactCreate, auth: Principal, db: Session, idempotency_key: str
) -> ArtifactOut:
    lock_write(db, auth, project_id)
    previous = replay(db, auth, project_id, "artifact.save", idempotency_key, body)
    if previous is not None:
        return ArtifactOut.model_validate(previous)
    existing = db.scalar(
        select(DeliveryArtifact).where(
            DeliveryArtifact.project_id == project_id,
            DeliveryArtifact.provider == "manual",
            DeliveryArtifact.kind == body.kind,
            DeliveryArtifact.external_id == body.external_id,
        )
    )
    if existing:
        if body.expected_revision != existing.revision:
            raise HTTPException(409, "Artifact changed; refresh before updating")
        (
            existing.title,
            existing.description,
            existing.status,
            existing.url,
            existing.executed_at,
            existing.environment,
            existing.updated_at,
        ) = (
            body.title,
            body.description,
            body.status,
            str(body.url) if body.url else None,
            body.executed_at,
            body.environment,
            datetime.now(UTC),
        )
        existing.revision += 1
        artifact = existing
    else:
        if body.expected_revision is not None:
            raise HTTPException(409, "Artifact no longer exists")
        artifact = DeliveryArtifact(
            project_id=project_id,
            provider="manual",
            kind=body.kind,
            external_id=body.external_id,
            title=body.title,
            description=body.description,
            status=body.status,
            url=str(body.url) if body.url else None,
            executed_at=body.executed_at,
            environment=body.environment,
        )
        db.add(artifact)
    db.flush()
    result = ArtifactOut.model_validate(artifact)
    db.add(
        ArtifactRevision(
            artifact_id=artifact.id,
            project_id=project_id,
            revision=artifact.revision,
            actor_id=auth.user.id,
            snapshot=result.model_dump(mode="json"),
        )
    )
    remember(db, auth, project_id, "artifact.save", idempotency_key, body, result)
    audit(
        db,
        auth.user,
        "artifact.recorded",
        artifact.id,
        project_id,
        kind=artifact.kind,
        external_id=artifact.external_id,
    )
    db.commit()
    return ArtifactOut.model_validate(artifact)


def artifacts(project_id: str, auth: Principal, db: Session, page: int = 1) -> list[ArtifactOut]:
    project_access(db, auth, project_id)
    return [
        ArtifactOut.model_validate(a)
        for a in db.scalars(
            select(DeliveryArtifact)
            .where(DeliveryArtifact.project_id == project_id)
            .order_by(DeliveryArtifact.updated_at.desc())
            .offset((page - 1) * 25)
            .limit(25)
        )
    ]


def create_link(
    project_id: str, body: LinkCreate, auth: Principal, db: Session, idempotency_key: str
) -> LinkOut:
    lock_write(db, auth, project_id, lead=body.accept)
    previous = replay(db, auth, project_id, "link.create", idempotency_key, body)
    if previous is not None:
        return LinkOut.model_validate(previous)
    req = db.scalar(
        select(BaselineItem).where(
            BaselineItem.project_id == project_id,
            BaselineItem.requirement_version_id == body.requirement_version_id,
        )
    )
    artifact = db.scalar(
        select(DeliveryArtifact).where(
            DeliveryArtifact.project_id == project_id, DeliveryArtifact.id == body.artifact_id
        )
    )
    if not req or not artifact:
        raise HTTPException(422, "Requirement version and artifact must belong to this project")
    if body.accept and body.expected_artifact_revision != artifact.revision:
        raise HTTPException(
            409, "Artifact changed or revision missing; inspect it before accepting"
        )
    existing = db.scalar(
        select(ArtifactLink).where(
            ArtifactLink.project_id == project_id,
            ArtifactLink.requirement_version_id == body.requirement_version_id,
            ArtifactLink.artifact_id == body.artifact_id,
        )
    )
    if existing:
        raise HTTPException(409, "This evidence link already exists")
    link = ArtifactLink(
        project_id=project_id,
        requirement_version_id=body.requirement_version_id,
        artifact_id=body.artifact_id,
        relation_type=body.relation_type,
        origin="manual",
        review_status="accepted" if body.accept else "proposed",
        reviewed_by=auth.user.id if body.accept else None,
        reviewed_at=datetime.now(UTC) if body.accept else None,
        artifact_revision=artifact.revision,
    )
    db.add(link)
    db.flush()
    if body.accept:
        db.add(
            LinkDecision(
                link_id=link.id,
                revision=link.revision,
                actor_id=auth.user.id,
                decision="accepted",
                artifact_revision=artifact.revision,
            )
        )
    remember(
        db, auth, project_id, "link.create", idempotency_key, body, LinkOut.model_validate(link)
    )
    audit(db, auth.user, "artifact.linked", link.id, project_id, review_status=link.review_status)
    db.commit()
    return LinkOut.model_validate(link)


def review_link(
    project_id: str, link_id: str, body: LinkReview, auth: Principal, db: Session
) -> LinkOut:
    lock_write(db, auth, project_id, lead=True)
    link = db.scalar(
        select(ArtifactLink)
        .where(ArtifactLink.project_id == project_id, ArtifactLink.id == link_id)
        .with_for_update()
    )
    if link is None:
        raise HTTPException(404, "Traceability link not found")
    if link.revision != body.expected_revision:
        raise HTTPException(409, "Link changed; refresh before deciding")
    artifact = db.get_one(DeliveryArtifact, link.artifact_id)
    if body.review_status == "accepted" and body.expected_artifact_revision != artifact.revision:
        raise HTTPException(
            409, "Artifact changed or revision missing; inspect it before accepting"
        )
    link.revision += 1
    link.artifact_revision = artifact.revision
    link.review_status, link.reviewed_by, link.reviewed_at = (
        body.review_status,
        auth.user.id,
        datetime.now(UTC),
    )
    db.add(
        LinkDecision(
            link_id=link.id,
            revision=link.revision,
            actor_id=auth.user.id,
            decision=link.review_status,
            artifact_revision=link.artifact_revision,
        )
    )
    audit(
        db,
        auth.user,
        "artifact.link_reviewed",
        link.id,
        project_id,
        review_status=link.review_status,
    )
    db.commit()
    return LinkOut.model_validate(link)


def review_links(
    project_id: str,
    body: BulkLinkReview,
    auth: Principal,
    db: Session,
    idempotency_key: str,
) -> BulkLinkReviewOut:
    lock_write(db, auth, project_id, lead=True)
    previous = replay(db, auth, project_id, "link.bulk_review", idempotency_key, body)
    if previous is not None:
        return BulkLinkReviewOut.model_validate(previous)
    ids = [decision.link_id for decision in body.decisions]
    rows = list(
        db.execute(
            select(ArtifactLink, DeliveryArtifact)
            .join(DeliveryArtifact, DeliveryArtifact.id == ArtifactLink.artifact_id)
            .where(ArtifactLink.project_id == project_id, ArtifactLink.id.in_(ids))
            .with_for_update()
        )
    )
    if len(rows) != len(ids):
        raise HTTPException(404, "One or more traceability links were not found")
    by_id = {link.id: (link, artifact) for link, artifact in rows}
    results: list[LinkOut] = []
    for decision in body.decisions:
        link, artifact = by_id[decision.link_id]
        if (
            link.revision != decision.expected_revision
            or artifact.revision != decision.expected_artifact_revision
        ):
            raise HTTPException(
                409, "A selected link or artifact changed; refresh before reviewing"
            )
    reviewed_at = datetime.now(UTC)
    for decision in body.decisions:
        link, artifact = by_id[decision.link_id]
        link.revision += 1
        link.artifact_revision = artifact.revision
        link.review_status = decision.review_status
        link.reviewed_by = auth.user.id
        link.reviewed_at = reviewed_at
        db.add(
            LinkDecision(
                link_id=link.id,
                revision=link.revision,
                actor_id=auth.user.id,
                decision=decision.review_status,
                artifact_revision=artifact.revision,
            )
        )
        audit(
            db,
            auth.user,
            "artifact.link_reviewed",
            link.id,
            project_id,
            review_status=decision.review_status,
            bulk=True,
        )
        results.append(
            LinkOut.model_validate(link).model_copy(
                update={
                    "stale": False,
                    "artifact_title": artifact.title,
                    "artifact_kind": artifact.kind,
                    "current_artifact_revision": artifact.revision,
                }
            )
        )
    output = BulkLinkReviewOut(items=results)
    remember(db, auth, project_id, "link.bulk_review", idempotency_key, body, output)
    db.commit()
    return output


def traceability(
    project_id: str, baseline_id: str, auth: Principal, db: Session, coverage: str = "all"
) -> list[TraceabilityOut]:
    project_access(db, auth, project_id)
    if (
        db.scalar(
            select(Baseline.id).where(Baseline.project_id == project_id, Baseline.id == baseline_id)
        )
        is None
    ):
        raise HTTPException(404, "Baseline not found")
    items = list(
        db.scalars(
            select(BaselineItem).where(
                BaselineItem.project_id == project_id, BaselineItem.baseline_id == baseline_id
            )
        )
    )
    grouped: dict[str, list[LinkOut]] = {}
    for link, artifact in db.execute(
        select(ArtifactLink, DeliveryArtifact)
        .join(DeliveryArtifact, ArtifactLink.artifact_id == DeliveryArtifact.id)
        .where(
            ArtifactLink.project_id == project_id,
            ArtifactLink.requirement_version_id.in_(
                [item.requirement_version_id for item in items]
            ),
        )
    ):
        grouped.setdefault(link.requirement_version_id, []).append(
            LinkOut.model_validate(link).model_copy(
                update={
                    "stale": link.artifact_revision != artifact.revision,
                    "artifact_title": artifact.title,
                    "artifact_kind": artifact.kind,
                    "current_artifact_revision": artifact.revision,
                }
            )
        )
    rows = [
        TraceabilityOut(
            requirement_version_id=item.requirement_version_id,
            links=grouped.get(item.requirement_version_id, []),
        )
        for item in items
    ]
    if coverage == "all":
        return rows
    return [
        row
        for row in rows
        if (
            (
                coverage == "current"
                and any(link.review_status == "accepted" and not link.stale for link in row.links)
            )
            or (
                coverage == "missing"
                and not any(
                    link.review_status == "accepted" and not link.stale for link in row.links
                )
            )
            or (coverage == "stale" and any(link.stale for link in row.links))
        )
    ]


def artifact_history(
    project_id: str, artifact_id: str, auth: Principal, db: Session, page: int = 1
) -> list[ArtifactOut]:
    project_access(db, auth, project_id)
    if (
        db.scalar(
            select(DeliveryArtifact.id).where(
                DeliveryArtifact.project_id == project_id, DeliveryArtifact.id == artifact_id
            )
        )
        is None
    ):
        raise HTTPException(404, "Artifact not found")
    return [
        ArtifactOut.model_validate(row.snapshot)
        for row in db.scalars(
            select(ArtifactRevision)
            .where(
                ArtifactRevision.project_id == project_id,
                ArtifactRevision.artifact_id == artifact_id,
            )
            .order_by(ArtifactRevision.revision.desc())
            .offset((page - 1) * 25)
            .limit(25)
        )
    ]
