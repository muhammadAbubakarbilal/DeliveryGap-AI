from typing import Literal, NoReturn

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.commands import lock_write, remember, replay
from app.requirement_models import (
    Baseline,
    BaselineItem,
    Requirement,
    RequirementLineage,
    RequirementReviewEvent,
    RequirementVersion,
)
from app.requirement_schemas import (
    BaselineCreate,
    BaselineItemOut,
    BaselineOut,
    RequirementCreate,
    RequirementEdit,
    RequirementLineageOut,
    RequirementOut,
    RequirementPage,
    RequirementTransform,
    RequirementTransformOut,
    RequirementVersionOut,
    ReviewInput,
)
from app.security import Principal, audit, project_access
from app.source_models import SourceSpan


def invalid_lineage_action() -> NoReturn:
    raise HTTPException(500, "Invalid requirement lineage action")


def lineage_output(lineage: RequirementLineage, codes: dict[str, str]) -> RequirementLineageOut:
    action: Literal["split", "merge"]
    if lineage.action == "split":
        action = "split"
    elif lineage.action == "merge":
        action = "merge"
    else:
        invalid_lineage_action()
    return RequirementLineageOut(
        id=lineage.id,
        action=action,
        parent_requirement_id=lineage.parent_requirement_id,
        parent_requirement_code=codes[lineage.parent_requirement_id],
        parent_version_id=lineage.parent_version_id,
        child_requirement_id=lineage.child_requirement_id,
        child_requirement_code=codes[lineage.child_requirement_id],
        child_version_id=lineage.child_version_id,
        created_at=lineage.created_at,
    )


def output(db: Session, row: Requirement) -> RequirementOut:
    versions = db.scalars(
        select(RequirementVersion)
        .where(
            RequirementVersion.project_id == row.project_id,
            RequirementVersion.requirement_id == row.id,
        )
        .order_by(RequirementVersion.version_number.desc())
    )
    lineage_rows = list(
        db.scalars(
            select(RequirementLineage)
            .where(
                RequirementLineage.project_id == row.project_id,
                (
                    (RequirementLineage.parent_requirement_id == row.id)
                    | (RequirementLineage.child_requirement_id == row.id)
                ),
            )
            .order_by(RequirementLineage.created_at, RequirementLineage.id)
        )
    )
    related_ids = {
        requirement_id
        for lineage in lineage_rows
        for requirement_id in (
            lineage.parent_requirement_id,
            lineage.child_requirement_id,
        )
    }
    codes: dict[str, str] = {}
    if related_ids:
        codes = {
            str(requirement_id): str(code)
            for requirement_id, code in db.execute(
                select(Requirement.id, Requirement.code).where(
                    Requirement.project_id == row.project_id,
                    Requirement.id.in_(related_ids),
                )
            )
        }
    return RequirementOut(
        id=row.id,
        code=row.code,
        current_version=row.current_version,
        status=row.status,
        versions=[RequirementVersionOut.model_validate(v) for v in versions],
        lineage=[lineage_output(lineage, codes) for lineage in lineage_rows],
    )


def get_requirement(db: Session, project: str, identity: str) -> Requirement:
    row = db.scalar(
        select(Requirement)
        .where(Requirement.project_id == project, Requirement.id == identity)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "Requirement not found")
    return row


def detail(db: Session, auth: Principal, project: str, identity: str) -> RequirementOut:
    project_access(db, auth, project)
    return output(db, get_requirement(db, project, identity))


def list_requirements(db: Session, auth: Principal, project: str, page: int) -> RequirementPage:
    project_access(db, auth, project)
    query = select(Requirement).where(Requirement.project_id == project)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Requirement.code).offset((page - 1) * 25).limit(25))
    return RequirementPage(items=[output(db, row) for row in rows], total=total)


def check_source(db: Session, project: str, body: RequirementCreate) -> None:
    if not body.title.strip() or not body.content.strip():
        raise HTTPException(422, "Title and requirement text are required")
    evidence = (body.source_version_id, body.source_span_id, body.source_quote)
    if not any(evidence):
        return
    if not all(evidence):
        raise HTTPException(422, "Source version, span, and nonempty quote are required together")
    span = db.scalar(
        select(SourceSpan).where(
            SourceSpan.project_id == project,
            SourceSpan.id == body.source_span_id,
            SourceSpan.version_id == body.source_version_id,
        )
    )
    if span is None or body.source_quote is None or body.source_quote not in span.text:
        raise HTTPException(422, "Source quote must align with a source span in this project")


def add_version(
    db: Session, auth: Principal, row: Requirement, body: RequirementCreate
) -> RequirementVersion:
    check_source(db, row.project_id, body)
    version = RequirementVersion(
        project_id=row.project_id,
        requirement_id=row.id,
        version_number=row.current_version,
        title=body.title,
        content=body.content,
        source_version_id=body.source_version_id,
        source_span_id=body.source_span_id,
        source_quote=body.source_quote,
        created_by=auth.user.id,
    )
    db.add(version)
    db.flush()
    return version


def create(
    db: Session, auth: Principal, project: str, body: RequirementCreate, key: str
) -> RequirementOut:
    lock_write(db, auth, project)
    previous = replay(db, auth, project, "requirement.create", key, body)
    if previous is not None:
        return RequirementOut.model_validate(previous)
    codes = list(db.scalars(select(Requirement.code).where(Requirement.project_id == project)))
    number = max((int(code[4:]) for code in codes), default=0) + 1
    code = body.code or f"REQ-{number:03d}"
    if code in codes:
        raise HTTPException(409, "Requirement code already exists")
    row = Requirement(project_id=project, code=code)
    db.add(row)
    db.flush()
    add_version(db, auth, row, body)
    result = output(db, row)
    remember(db, auth, project, "requirement.create", key, body, result)
    audit(db, auth.user, "requirement.created", row.id, project)
    db.commit()
    return result


def edit(
    db: Session, auth: Principal, project: str, identity: str, body: RequirementEdit, key: str
) -> RequirementOut:
    lock_write(db, auth, project)
    operation = "requirement.edit:" + identity
    previous = replay(db, auth, project, operation, key, body)
    if previous is not None:
        return RequirementOut.model_validate(previous)
    row = get_requirement(db, project, identity)
    if row.status != "active":
        raise HTTPException(409, "Superseded requirements cannot be revised")
    if row.current_version != body.expected_version:
        raise HTTPException(409, "Requirement changed; refresh before editing")
    if body.code and body.code != row.code:
        raise HTTPException(422, "A requirement's stable code cannot change")
    row.current_version += 1
    add_version(db, auth, row, body)
    result = output(db, row)
    remember(db, auth, project, operation, key, body, result)
    audit(db, auth.user, "requirement.revised", row.id, project, version=row.current_version)
    db.commit()
    return result


def review(
    db: Session, auth: Principal, project: str, identity: str, body: ReviewInput, decision: str
) -> RequirementOut:
    lock_write(db, auth, project, lead=True)
    row = get_requirement(db, project, identity)
    if row.status != "active":
        raise HTTPException(409, "Superseded requirements cannot be reviewed")
    version = db.scalar(
        select(RequirementVersion).where(
            RequirementVersion.requirement_id == row.id,
            RequirementVersion.version_number == body.expected_version,
        )
    )
    if row.current_version != body.expected_version or version is None or version.status != "draft":
        raise HTTPException(409, "Requirement has changed or already been reviewed; refresh")
    if decision == "approved":
        if not version.source_quote or not version.source_span_id:
            raise HTTPException(422, "Source evidence is required before approval")
        check_source(
            db,
            project,
            RequirementCreate(
                title=version.title,
                content=version.content,
                source_version_id=version.source_version_id,
                source_span_id=version.source_span_id,
                source_quote=version.source_quote,
            ),
        )
    version.status = decision
    db.add(
        RequirementReviewEvent(
            project_id=project,
            requirement_version_id=version.id,
            actor_id=auth.user.id,
            action=decision,
            expected_version=body.expected_version,
        )
    )
    audit(db, auth.user, "requirement." + decision, version.id, project)
    db.flush()
    result = output(db, row)
    db.commit()
    return result


def transform(
    db: Session,
    auth: Principal,
    project: str,
    body: RequirementTransform,
    key: str,
) -> RequirementTransformOut:
    lock_write(db, auth, project, lead=True)
    previous = replay(db, auth, project, "requirement.transform", key, body)
    if previous is not None:
        return RequirementTransformOut.model_validate(previous)
    parents: list[tuple[Requirement, RequirementVersion]] = []
    for parent in body.parents:
        row = get_requirement(db, project, parent.requirement_id)
        if row.status != "active" or row.current_version != parent.expected_version:
            raise HTTPException(409, "A parent requirement changed or was already superseded")
        version = db.scalar(
            select(RequirementVersion).where(
                RequirementVersion.project_id == project,
                RequirementVersion.requirement_id == row.id,
                RequirementVersion.version_number == parent.expected_version,
            )
        )
        if version is None or version.status == "rejected":
            raise HTTPException(409, "A parent requirement has no current usable revision")
        parents.append((row, version))
    for parent_row, _ in parents:
        parent_row.status = "superseded"
    existing_codes = set(
        db.scalars(select(Requirement.code).where(Requirement.project_id == project))
    )
    next_number = (
        max(
            (
                int(code[4:])
                for code in existing_codes
                if code.startswith("REQ-") and code[4:].isdigit()
            ),
            default=0,
        )
        + 1
    )
    children: list[Requirement] = []
    for child_body in body.children:
        if (
            not child_body.source_version_id
            or not child_body.source_span_id
            or not child_body.source_quote
        ):
            raise HTTPException(422, "Every transformed requirement needs exact source evidence")
        check_source(db, project, child_body)
        while child_body.code is None and f"REQ-{next_number:03d}" in existing_codes:
            next_number += 1
        code = child_body.code or f"REQ-{next_number:03d}"
        if code in existing_codes:
            raise HTTPException(409, "A child requirement code already exists")
        existing_codes.add(code)
        if child_body.code is None:
            next_number += 1
        child_row = Requirement(project_id=project, code=code)
        db.add(child_row)
        db.flush()
        child_version = add_version(db, auth, child_row, child_body)
        children.append(child_row)
        for parent_row, parent_version in parents:
            db.add(
                RequirementLineage(
                    project_id=project,
                    action=body.action,
                    parent_requirement_id=parent_row.id,
                    parent_version_id=parent_version.id,
                    child_requirement_id=child_row.id,
                    child_version_id=child_version.id,
                    actor_id=auth.user.id,
                )
            )
    db.flush()
    for parent_row, _ in parents:
        audit(
            db,
            auth.user,
            f"requirement.{body.action}",
            parent_row.id,
            project,
            child_ids=[child.id for child in children],
        )
    result = RequirementTransformOut(
        superseded_requirement_ids=[row.id for row, _ in parents],
        children=[output(db, child) for child in children],
    )
    remember(db, auth, project, "requirement.transform", key, body, result)
    db.commit()
    return result


def baseline_output(db: Session, row: Baseline) -> BaselineOut:
    items = db.scalars(
        select(BaselineItem)
        .where(BaselineItem.project_id == row.project_id, BaselineItem.baseline_id == row.id)
        .order_by(BaselineItem.requirement_code)
    )
    return BaselineOut(
        id=row.id,
        number=row.number,
        status=row.status,
        published_by=row.published_by,
        created_at=row.created_at,
        items=[BaselineItemOut.model_validate(item) for item in items],
    )


def publish(
    db: Session, auth: Principal, project: str, body: BaselineCreate, key: str
) -> BaselineOut:
    lock_write(db, auth, project, lead=True)
    previous = replay(db, auth, project, "baseline.publish", key, body)
    if previous is not None:
        return BaselineOut.model_validate(previous)
    ids = body.requirement_version_ids
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Choose unique requirement versions")
    versions = list(
        db.scalars(
            select(RequirementVersion).where(
                RequirementVersion.project_id == project, RequirementVersion.id.in_(ids)
            )
        )
    )
    if len(versions) != len(ids) or any(v.status != "approved" for v in versions):
        raise HTTPException(422, "Only approved requirement versions in this project are allowed")
    if len({v.requirement_id for v in versions}) != len(versions):
        raise HTTPException(422, "Choose only one revision of each requirement")
    number = (
        db.scalar(select(func.max(Baseline.number)).where(Baseline.project_id == project)) or 0
    ) + 1
    row = Baseline(project_id=project, number=number, published_by=auth.user.id)
    db.add(row)
    db.flush()
    for version in versions:
        req = get_requirement(db, project, version.requirement_id)
        if req.status != "active":
            raise HTTPException(422, "Superseded requirements cannot be added to a new baseline")
        db.add(
            BaselineItem(
                baseline_id=row.id,
                project_id=project,
                requirement_version_id=version.id,
                requirement_code=req.code,
            )
        )
    db.flush()
    result = baseline_output(db, row)
    remember(db, auth, project, "baseline.publish", key, body, result)
    audit(db, auth.user, "baseline.published", row.id, project, number=number)
    db.commit()
    return result


def list_baselines(db: Session, auth: Principal, project: str, page: int) -> list[BaselineOut]:
    project_access(db, auth, project)
    return [
        baseline_output(db, row)
        for row in db.scalars(
            select(Baseline)
            .where(Baseline.project_id == project)
            .order_by(Baseline.number.desc())
            .offset((page - 1) * 25)
            .limit(25)
        )
    ]


def baseline_detail(db: Session, auth: Principal, project: str, identity: str) -> BaselineOut:
    project_access(db, auth, project)
    row = db.scalar(select(Baseline).where(Baseline.project_id == project, Baseline.id == identity))
    if row is None:
        raise HTTPException(404, "Baseline not found")
    return baseline_output(db, row)
