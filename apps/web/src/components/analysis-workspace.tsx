"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, message, type Project } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "./shell";
import { GroundedAnalysis } from "./grounded-analysis";
import { ManualChange } from "./manual-change";

type Run = components["schemas"]["AnalysisOut"];
type Baseline = components["schemas"]["BaselineOut"];
type Finding = components["schemas"]["FindingOut"];

export function AnalysisWorkspace({ projectId }: { projectId: string }) {
  const session = useSession();
  const base = `/projects/${projectId}`;
  const [project, setProject] = useState<Project | null>(null);
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [page, setPage] = useState(1);
  const [baselinePage, setBaselinePage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const command = useRef<{ payload: string; key: string } | null>(null);
  const canWrite = project?.status === "active" && (session.user.is_admin || project.role === "lead" || project.role === "member");
  const canReview = canWrite && (session.user.is_admin || project?.role === "lead");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<Project>(base, { signal: controller.signal }),
      api<Baseline[]>(`${base}/baselines?page=${baselinePage}`, { signal: controller.signal }),
      api<Run[]>(`${base}/analysis?page=${page}`, { signal: controller.signal }),
    ]).then(([p, b, r]) => { setProject(p); setBaselines(b); setRuns(r); })
      .catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [base, page, baselinePage, refresh]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const payload = JSON.stringify({ baseline_id: data.get("baseline"), input_text: "Add EUR and GBP checkout.", provider: "fixture" });
    if (command.current?.payload !== payload) command.current = { payload, key: crypto.randomUUID() };
    setBusy(true); setError(""); setNotice("");
    try {
      await api(base + "/analysis", { method: "POST", body: payload, headers: { "Idempotency-Key": command.current.key } }, session.csrf_token);
      command.current = null; setRefresh(n => n + 1); setNotice("Synthetic fixture replay saved.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function decide(finding: Finding, decision: string) {
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`${base}/findings/${finding.id}/decision`, { method: "POST", body: JSON.stringify({ decision, expected_status: finding.review_status, expected_revision: finding.revision }) }, session.csrf_token);
      setRefresh(n => n + 1); setNotice("Reviewer decision recorded.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <>
    <Link className="back-link" href={`/projects/${projectId}`}>Back to project</Link>
    <div className="page-heading"><div><h1>Change findings</h1><p>Findings are proposals. A lead must review the evidence before recording a decision.</p></div></div>
    <ManualChange projectId={projectId} baselines={baselines} canWrite={canWrite} onSaved={() => {setPage(1); setRefresh(n => n + 1);}} />
    <GroundedAnalysis projectId={projectId} baselines={baselines} canWrite={canWrite} canCancel={canReview} externalAiConsent={project?.external_ai_consent === true} onComplete={() => {setPage(1); setRefresh(n => n + 1);}} />
    <section className="panel"><h2>Synthetic demonstration only</h2><p>This fixture replays one known currency conflict; it does not classify arbitrary requests or measure AI quality.</p>
      <p>Use a baseline containing only “Checkout accepts USD payments only.” with that exact source quote. The synthetic request is “Add EUR and GBP checkout.”</p>
      {canWrite && <form className="stack" onSubmit={create}><label>Baseline<select name="baseline" required><option value="">Choose a baseline</option>{baselines.map(b => <option key={b.id} value={b.id}>B{b.number}</option>)}</select></label>
        <div><button type="button" disabled={baselinePage === 1} onClick={() => setBaselinePage(p => p - 1)}>Previous baselines</button> Page {baselinePage} <button type="button" disabled={baselines.length < 25} onClick={() => setBaselinePage(p => p + 1)}>Next baselines</button></div>
        <button className="primary" disabled={busy}>Replay synthetic fixture</button>
      </form>}
    </section>
    {error && <div role="alert" className="alert">{error} <button onClick={() => { setError(""); setRefresh(n => n + 1); }}>Refresh</button></div>}
    {notice && <p role="status" className="success">{notice}</p>}
    {!project && !error && <p role="status">Loading findings…</p>}
    {project && !runs.length && <p>No saved analysis runs on this page.</p>}
    {runs.map(run => <section className="panel" key={run.id}><h2>{run.provider === "fixture" ? "Fixture run" : run.provider === "neon-hybrid" ? "Hybrid AI proposal" : "Analysis run"} · {new Date(run.created_at).toLocaleString()}</h2><p>{run.warning}</p>
      {run.input_text && <><h3>Submitted change request</h3><blockquote>{run.input_text}</blockquote></>}
      {run.outcome === "no_actionable_requests" && <p role="status">Analysis completed successfully. No actionable software changes were identified.</p>}
      {run.outcome === "partial" && <p role="status">Analysis completed with partial results. Check the analysis job for request-level failures before retrying.</p>}
      {run.findings.map(f => <article key={f.id}><h3>{f.classification.replaceAll("_", " ")}</h3><p>{f.summary}</p>{f.evidence_quote && <blockquote>{f.evidence_quote}</blockquote>}<p>Review: {f.review_status.replaceAll("_", " ")}</p>
        {f.input_quote && <><h4>Change request evidence{f.request_index !== null && f.request_index !== undefined ? ` · request ${f.request_index + 1}` : ""}</h4>
          {f.input_span_start !== null && f.input_span_start !== undefined && f.input_span_end !== null && f.input_span_end !== undefined
            && <p>Source characters {f.input_span_start}–{f.input_span_end} (zero-based Unicode code-point offsets; end is exclusive).</p>}
          <blockquote>{f.input_quote}</blockquote></>}
        {canReview && <div><button disabled={busy} onClick={() => void decide(f, "confirmed")}>Confirm proposal</button>{" "}<button disabled={busy} onClick={() => void decide(f, "dismissed")}>Dismiss proposal</button>{" "}<button disabled={busy} onClick={() => void decide(f, "clarification_requested")}>Request clarification</button></div>}
      </article>)}
    </section>)}
    <nav aria-label="Analysis pages"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous runs</button> Page {page} <button disabled={runs.length < 25} onClick={() => setPage(p => p + 1)}>Next runs</button></nav>
  </>;
}
