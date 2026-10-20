from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis_models import AnalysisRun, Finding, FindingDecision
from app.analysis_schemas import (
    AnalysisCreate,
    AnalysisOut,
    BaselineCitation,
    FindingDecisionIn,
    FindingOut,
    ManualAnalysisCreate,
)
from app.commands import lock_write, remember, replay
from app.requirement_models import Baseline, BaselineItem, RequirementVersion
from app.security import Principal, audit, project_access


def classify(text: str, version: RequirementVersion) -> tuple[str, str]:
    # Deliberately exact: this development fixture is not a general classifier.
    if (
        text == "Add EUR and GBP checkout."
        and version.content == "Checkout accepts USD payments only."
        and version.source_quote == "Checkout accepts USD payments only."
    ):
        return (
            "CONFLICT",
            "Synthetic fixture proposal: EUR/GBP contradict the approved USD-only provision.",
        )
    raise HTTPException(
        422, "Unknown fixture. Only the documented synthetic currency case is supported."
    )


def create_analysis(
    project_id: str, body: AnalysisCreate, auth: Principal, db: Session, idempotency_key: str
) -> AnalysisOut:
    lock_write(db, auth, project_id)
    previous = replay(db, auth, project_id, "analysis.fixture", idempotency_key, body)
    if previous is not None:
        return AnalysisOut.model_validate(previous)
    baseline = db.scalar(
        select(Baseline).where(Baseline.project_id == project_id, Baseline.id == body.baseline_id)
    )
    if baseline is None:
        raise HTTPException(404, "Baseline not found")
    run = AnalysisRun(
        project_id=project_id,
        baseline_id=baseline.id,
        actor_id=auth.user.id,
        input_text=body.input_text,
    )
    db.add(run)
    db.flush()
    items = list(
        db.scalars(
            select(BaselineItem).where(
                BaselineItem.project_id == project_id, BaselineItem.baseline_id == baseline.id
            )
        )
    )
    findings: list[Finding] = []
    if len(items) != 1:
        raise HTTPException(
            422, "This fixture requires a baseline containing only the USD checkout requirement."
        )
    for item in items:
        version = db.get(RequirementVersion, item.requirement_version_id)
        if version is None:
            continue
        classification, summary = classify(body.input_text, version)
        findings.append(
            Finding(
                project_id=project_id,
                run_id=run.id,
                classification=classification,
                summary=summary,
                requirement_version_id=version.id,
                evidence_quote=version.source_quote,
            )
        )
    if not findings:
        findings.append(
            Finding(
                project_id=project_id,
                run_id=run.id,
                classification="INSUFFICIENT_EVIDENCE",
                summary="The baseline contains no retrievable approved requirements.",
                requirement_version_id=None,
                evidence_quote=None,
            )
        )
    db.add_all(findings)
    db.flush()
    result = AnalysisOut(
        id=run.id,
        baseline_id=run.baseline_id,
        status=run.status,
        created_at=run.created_at,
        findings=[FindingOut.model_validate(f) for f in findings],
    )
    remember(db, auth, project_id, "analysis.fixture", idempotency_key, body, result)
    audit(db, auth.user, "analysis.created", run.id, project_id, baseline_id=baseline.id)
    db.commit()
    return AnalysisOut(
        id=run.id,
        baseline_id=run.baseline_id,
        status=run.status,
        created_at=run.created_at,
        findings=[FindingOut.model_validate(f) for f in findings],
    )


def decide(
    project_id: str, finding_id: str, body: FindingDecisionIn, auth: Principal, db: Session
) -> FindingOut:
    lock_write(db, auth, project_id, lead=True)
    finding = db.scalar(
        select(Finding)
        .where(Finding.project_id == project_id, Finding.id == finding_id)
        .with_for_update()
    )
    if finding is None:
        raise HTTPException(404, "Finding not found")
    if finding.review_status != body.expected_status or finding.revision != body.expected_revision:
        raise HTTPException(409, "Finding changed; refresh before deciding")
    finding.revision += 1
    finding.review_status = body.decision
    db.add(
        FindingDecision(
            project_id=project_id,
            finding_id=finding.id,
            actor_id=auth.user.id,
            decision=body.decision,
            expected_status=body.expected_status,
        )
    )
    audit(db, auth.user, "finding.decided", finding.id, project_id, decision=body.decision)
    db.commit()
    return FindingOut.model_validate(finding)


def run_output(db: Session, run: AnalysisRun) -> AnalysisOut:
    return AnalysisOut(
        input_text=run.input_text,
        provider=run.provider,
        outcome=cast(Literal["completed", "partial", "no_actionable_requests"], run.outcome),
        warning=(
            "Human-authored proposal; no AI was used. "
            "A lead must review its reasoning and evidence."
            if run.provider == "manual"
            else "No actionable software changes were identified; no findings were produced."
            if run.outcome == "no_actionable_requests"
            else "Some atomic requests could not be analyzed. Review successful findings and "
            "the job's per-request status before retrying."
            if run.outcome == "partial"
            else "Synthetic fixture replay only. Live AI and quality evaluation are not enabled."
            if run.provider == "fixture"
            else "Hybrid BM25 and vector retrieval. Scores are not confidence values; "
            "quality is unmeasured until human-reviewed held-out evaluation."
            if run.provider == "neon-hybrid"
            else "Lexical retrieval proposals require human review. Model quality is unmeasured."
            if run.provider == "neon-lexical"
            else "Legacy heuristic result. This result was not produced by a grounded AI pipeline."
        ),
        id=run.id,
        baseline_id=run.baseline_id,
        status=run.status,
        created_at=run.created_at,
        findings=[
            FindingOut.model_validate(f)
            for f in db.scalars(
                select(Finding)
                .where(Finding.project_id == run.project_id, Finding.run_id == run.id)
                .order_by(Finding.request_index, Finding.id)
            )
        ],
    )


def baseline_citations(
    project_id: str, baseline_id: str, auth: Principal, db: Session
) -> list[BaselineCitation]:
    project_access(db, auth, project_id)
    baseline = db.scalar(
        select(Baseline).where(Baseline.id == baseline_id, Baseline.project_id == project_id)
    )
    if baseline is None:
        raise HTTPException(404, "Baseline not found")
    return [
        BaselineCitation(
            requirement_version_id=version.id,
            requirement_code=item.requirement_code,
            title=version.title,
            content=version.content,
            source_quote=version.source_quote,
        )
        for item, version in db.execute(
            select(BaselineItem, RequirementVersion)
            .join(RequirementVersion, RequirementVersion.id == BaselineItem.requirement_version_id)
            .where(
                BaselineItem.baseline_id == baseline_id,
                BaselineItem.project_id == project_id,
                RequirementVersion.project_id == project_id,
            )
            .order_by(BaselineItem.requirement_code)
        )
    ]


def create_manual(
    project_id: str, body: ManualAnalysisCreate, auth: Principal, db: Session, key: str
) -> AnalysisOut:
    lock_write(db, auth, project_id)
    previous = replay(db, auth, project_id, "analysis.manual", key, body)
    if previous is not None:
        return AnalysisOut.model_validate(previous)
    citations = baseline_citations(project_id, body.baseline_id, auth, db)
    citation = next(
        (c for c in citations if c.requirement_version_id == body.requirement_version_id), None
    )
    supported = body.classification in {"IN_SCOPE", "CONFLICT", "POTENTIAL_SCOPE_ADDITION"}
    if supported or body.requirement_version_id or body.evidence_quote:
        if (
            citation is None
            or not citation.source_quote
            or not body.evidence_quote
            or body.evidence_quote not in citation.source_quote
        ):
            raise HTTPException(
                422, "Select a requirement from this baseline and cite an exact source quote"
            )
    run = AnalysisRun(
        project_id=project_id,
        baseline_id=body.baseline_id,
        actor_id=auth.user.id,
        input_text=body.input_text,
        provider="manual",
    )
    db.add(run)
    db.flush()
    db.add(
        Finding(
            project_id=project_id,
            run_id=run.id,
            classification=body.classification,
            summary=body.summary,
            requirement_version_id=body.requirement_version_id,
            evidence_quote=body.evidence_quote,
        )
    )
    db.flush()
    result = run_output(db, run)
    remember(db, auth, project_id, "analysis.manual", key, body, result)
    audit(db, auth.user, "analysis.manual_created", run.id, project_id)
    db.commit()
    return result


def analyses(
    project_id: str,
    auth: Principal,
    db: Session,
    page: int = 1,
    baseline_id: str | None = None,
) -> list[AnalysisOut]:
    project_access(db, auth, project_id)
    query = select(AnalysisRun).where(AnalysisRun.project_id == project_id)
    if baseline_id is not None:
        if (
            db.scalar(
                select(Baseline.id).where(
                    Baseline.project_id == project_id, Baseline.id == baseline_id
                )
            )
            is None
        ):
            raise HTTPException(404, "Baseline not found")
        query = query.where(AnalysisRun.baseline_id == baseline_id)
    return [
        run_output(db, run)
        for run in db.scalars(
            query.order_by(AnalysisRun.created_at.desc()).offset((page - 1) * 25).limit(25)
        )
    ]


def analysis_detail(project_id: str, run_id: str, auth: Principal, db: Session) -> AnalysisOut:
    project_access(db, auth, project_id)
    run = db.scalar(
        select(AnalysisRun).where(AnalysisRun.project_id == project_id, AnalysisRun.id == run_id)
    )
    if run is None:
        raise HTTPException(404, "Analysis not found")
    return run_output(db, run)
