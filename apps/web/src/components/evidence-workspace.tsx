"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, message, type Project } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "./shell";
import { ImportsReports } from "./imports-reports";

type Artifact = components["schemas"]["ArtifactOut"];
type Baseline = components["schemas"]["BaselineOut"];
type Trace = components["schemas"]["TraceabilityOut"];

function localDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function EvidenceWorkspace({ projectId }: { projectId: string }) {
  const session = useSession();
  const base = `/projects/${projectId}`;
  const [project, setProject] = useState<Project | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [baselineId, setBaselineId] = useState("");
  const [coverage, setCoverage] = useState("all");
  const [matrix, setMatrix] = useState<Trace[]>([]);
  const [selectedLinks, setSelectedLinks] = useState<Record<string, boolean>>({});
  const [page, setPage] = useState(1);
  const [baselinePage, setBaselinePage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [editing, setEditing] = useState<Artifact | null>(null);
  const [kind, setKind] = useState<Artifact["kind"]>("task");
  const [history, setHistory] = useState<Artifact[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const command = useRef<{ signature: string; key: string } | null>(null);
  const canWrite = project?.status === "active" && (session.user.is_admin || project.role === "lead" || project.role === "member");
  const canReview = canWrite && (session.user.is_admin || project?.role === "lead");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<Project>(base, { signal: controller.signal }),
      api<Artifact[]>(`${base}/artifacts?page=${page}`, { signal: controller.signal }),
      api<Baseline[]>(`${base}/baselines?page=${baselinePage}`, { signal: controller.signal }),
    ]).then(([p, a, b]) => { setProject(p); setArtifacts(a); setBaselines(b); })
      .catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [base, page, baselinePage, refresh]);
  useEffect(() => {
    if (!baselineId) return;
    const controller = new AbortController();
    api<Trace[]>(`${base}/traceability?baseline_id=${baselineId}&coverage=${coverage}`, { signal: controller.signal }).then(setMatrix)
      .catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [base, baselineId, refresh, coverage]);
  async function mutate(path: string, body: object) {
    const payload = JSON.stringify(body);
    const signature = path + payload;
    if (command.current?.signature !== signature) command.current = { signature, key: crypto.randomUUID() };
    setBusy(true); setError(""); setNotice("");
    try {
      await api(base + path, { method: "POST", body: payload, headers: { "Idempotency-Key": command.current.key } }, session.csrf_token);
      command.current = null; setRefresh(n => n + 1); setNotice("Saved."); return true;
    } catch (e) { setError(message(e)); return false; } finally { setBusy(false); }
  }
  async function saveArtifact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const executionTime = String(form.get("executed_at") ?? "");
    const body = {
      kind,
      external_id: editing?.external_id ?? form.get("external_id"),
      title: form.get("title"),
      description: form.get("description"),
      status: form.get("status"),
      url: form.get("url") || null,
      executed_at: kind === "test" && executionTime ? new Date(executionTime).toISOString() : null,
      environment: kind === "test" ? String(form.get("environment") || "") || null : null,
      expected_revision: editing?.revision ?? null,
    };
    if (await mutate("/artifacts", body)) {
      setEditing(null);
      setKind("task");
    }
  }
  async function linkArtifact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    await mutate("/traceability/links", { requirement_version_id: form.get("requirement"), artifact_id: form.get("artifact"), accept: form.get("accept") === "on", expected_artifact_revision: artifacts.find(a => a.id === form.get("artifact"))?.revision });
  }
  const baseline = baselines.find(b => b.id === baselineId);
  return <>
    <Link className="back-link" href={`/projects/${projectId}`}>Back to project</Link>
    <div className="page-heading"><div><h1>Delivery evidence</h1><p>Record delivery artifacts and review their links to approved scope. Missing evidence is not proof of missing implementation.</p></div></div>
    {error && <p role="alert" className="alert">{error} <button onClick={() => { setError(""); setRefresh(n => n + 1); }}>Refresh</button></p>}
    {notice && <p role="status" className="success">{notice}</p>}
    {!project && !error && <p role="status">Loading evidence…</p>}
    {canWrite && <section className="panel"><h2>{editing ? "Revise artifact" : "Record artifact"}</h2>
      <form key={editing?.id ?? "new"} onSubmit={saveArtifact} className="stack">
        <label>Kind<select name="kind" value={kind} onChange={event => setKind(event.target.value as Artifact["kind"])} disabled={busy || !!editing}><option value="task">Task</option><option value="test">Test</option><option value="pull_request">Pull request</option></select></label>
        <label>External identifier<input name="external_id" required maxLength={120} defaultValue={editing?.external_id} readOnly={!!editing} /></label>
        <label>Title<input name="title" required maxLength={300} defaultValue={editing?.title} /></label>
        <label>Description<textarea name="description" maxLength={20000} defaultValue={editing?.description} /></label>
        <label>Status or test result<input name="status" required maxLength={32} defaultValue={editing?.status ?? "recorded"} /></label>
        {kind === "test" && <>
          <label>Execution time<input name="executed_at" type="datetime-local" defaultValue={localDateTime(editing?.executed_at)} /></label>
          <label>Test environment<input name="environment" maxLength={200} defaultValue={editing?.environment ?? ""} placeholder="e.g. staging · Chrome 130 · Windows" /></label>
          <p>Execution time is recorded with your local timezone offset.</p>
        </>}
        <label>Evidence URL<input name="url" type="url" defaultValue={editing?.url ?? ""} /></label>
        <div><button className="primary" disabled={busy}>Save artifact</button>{editing && <button type="button" onClick={() => { setEditing(null); setKind("task"); }}>Cancel revision</button>}</div>
      </form></section>}
    <section className="panel"><h2>Artifacts</h2>{artifacts.length ? artifacts.map(a => <details key={a.id}><summary>{a.external_id} · {a.title} · {a.status}</summary><p>{a.description}</p><p>Revision {a.revision}</p>{a.executed_at && <p>Executed {new Date(a.executed_at).toLocaleString()}{a.environment ? ` · ${a.environment}` : ""}</p>}{a.url && <a href={a.url} target="_blank" rel="noopener noreferrer">Open evidence</a>}
      {canWrite && a.provider === "manual" && <button disabled={busy} onClick={() => { setEditing(a); setKind(a.kind); }}>Revise</button>}{a.provider === "csv" && <p>Revise this artifact by previewing and importing an updated CSV.</p>}
      <button onClick={async () => { try { setHistory(await api<Artifact[]>(`${base}/artifacts/${a.id}/history`)); } catch (e) { setError(message(e)); } }}>View recent history</button>
    </details>) : <p>No artifacts on this page.</p>}
      <nav aria-label="Artifact pages"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button> Page {page} <button disabled={artifacts.length < 25} onClick={() => setPage(p => p + 1)}>Next</button></nav>
      {history.length > 0 && <div><h3>Recent artifact revisions</h3>{history.map(a => <p key={a.revision}>v{a.revision}: {a.title} · {a.status} · {a.description}{a.executed_at && ` · Executed ${new Date(a.executed_at).toLocaleString()}`}{a.environment && ` · ${a.environment}`}</p>)}</div>}
    </section>
    <section className="panel"><h2>Traceability</h2><label>Evidence coverage<select value={coverage} onChange={e => { setCoverage(e.target.value); setSelectedLinks({}); }}><option value="all">All requirements</option><option value="current">Accepted current evidence</option><option value="missing">Without accepted current evidence</option><option value="stale">Changed evidence</option></select></label>
      <label>Published baseline<select value={baselineId} onChange={e => { setBaselineId(e.target.value); setMatrix([]); setSelectedLinks({}); }}><option value="">Select a baseline</option>{baselines.map(b => <option key={b.id} value={b.id}>B{b.number}</option>)}</select></label>
      <nav aria-label="Baseline pages"><button disabled={baselinePage === 1} onClick={() => { setBaselinePage(p => p - 1); setBaselineId(""); setMatrix([]); }}>Previous baselines</button> Page {baselinePage} <button disabled={baselines.length < 25} onClick={() => { setBaselinePage(p => p + 1); setBaselineId(""); setMatrix([]); }}>Next baselines</button></nav>
      {canWrite && baseline && <form onSubmit={linkArtifact} className="stack">
        <label>Requirement<select name="requirement" required>{baseline.items.map(i => <option key={i.requirement_version_id} value={i.requirement_version_id}>{i.requirement_code}</option>)}</select></label>
        <label>Artifact on current page<select name="artifact" required><option value="">Select artifact</option>{artifacts.map(a => <option key={a.id} value={a.id}>{a.external_id} · {a.title}</option>)}</select></label>
        {canReview && <label className="source-toggle"><input type="checkbox" name="accept" /> Accept this link when saving</label>}
        <button className="primary" disabled={busy}>Link evidence</button>
      </form>}
      {baseline && matrix.map(row => <section key={row.requirement_version_id}><h3>{baseline.items.find(i => i.requirement_version_id === row.requirement_version_id)?.requirement_code}</h3>
        {!row.links.length && <p>No linked evidence recorded.</p>}
        {row.links.map(link => <div key={link.id}><p>{link.artifact_title ?? "Unknown artifact"} · {link.review_status} · inspected revision {link.artifact_revision ?? "unknown"}{link.stale && " · Evidence changed — review again"}</p>
          {canReview && <label><input type="checkbox" checked={selectedLinks[link.id] ?? false} onChange={event => setSelectedLinks(previous => ({ ...previous, [link.id]: event.target.checked }))} /> Select for bulk review</label>}
          {canReview && <div><button disabled={busy} onClick={() => void mutate(`/traceability/links/${link.id}/review`, { review_status: "accepted", expected_revision: link.revision, expected_artifact_revision: link.current_artifact_revision })}>Accept</button> <button disabled={busy} onClick={() => void mutate(`/traceability/links/${link.id}/review`, { review_status: "rejected", expected_revision: link.revision })}>Reject</button></div>}
        </div>)}
      </section>)}
      {canReview && Object.values(selectedLinks).filter(Boolean).length > 0 && <div className="panel">
        <p>{Object.values(selectedLinks).filter(Boolean).length} links selected. Bulk review is limited to 100 links and rejects the entire command if any selected revision has changed.</p>
        <button disabled={busy || Object.values(selectedLinks).filter(Boolean).length > 100} onClick={async () => {
          const chosen = matrix.flatMap(row => row.links).filter(link => selectedLinks[link.id]);
          if (chosen.some(link => typeof link.current_artifact_revision !== "number")) {
            setError("A selected artifact revision is unknown. Refresh the traceability matrix before reviewing.");
            return;
          }
          if (await mutate("/traceability/links/bulk-review", {
            decisions: chosen.map(link => ({
              link_id: link.id,
              expected_revision: link.revision,
              expected_artifact_revision: link.current_artifact_revision,
              review_status: "accepted",
            })),
          })) setSelectedLinks({});
        }}>Accept selected links</button>{" "}
        <button disabled={busy || Object.values(selectedLinks).filter(Boolean).length > 100} onClick={async () => {
          const chosen = matrix.flatMap(row => row.links).filter(link => selectedLinks[link.id]);
          if (chosen.some(link => typeof link.current_artifact_revision !== "number")) {
            setError("A selected artifact revision is unknown. Refresh the traceability matrix before reviewing.");
            return;
          }
          if (await mutate("/traceability/links/bulk-review", {
            decisions: chosen.map(link => ({
              link_id: link.id,
              expected_revision: link.revision,
              expected_artifact_revision: link.current_artifact_revision,
              review_status: "rejected",
            })),
          })) setSelectedLinks({});
        }}>Reject selected links</button>{" "}
        <button disabled={busy} onClick={() => setSelectedLinks({})}>Clear selection</button>
      </div>}
    </section>
    {project && <ImportsReports projectId={projectId} baselineId={baselineId} canWrite={canWrite} refreshVersion={refresh} onImported={() => setRefresh(n => n + 1)} />}
  </>;
}
