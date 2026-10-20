"use client";

import { useEffect, useRef, useState } from "react";
import { api, message } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "./shell";

type Operation = components["schemas"]["OperationOut"];
type Preview = components["schemas"]["PreviewOut"];
type Overview = components["schemas"]["OverviewOut"];
type Run = components["schemas"]["AnalysisOut"];

export function ImportsReports({ projectId, baselineId, canWrite, onImported, refreshVersion }: {
  projectId: string; baselineId: string; canWrite: boolean; onImported: () => void; refreshVersion: number;
}) {
  const session = useSession();
  const base = `/projects/${projectId}`;
  const [kind, setKind] = useState<"task" | "test">("task");
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [partial, setPartial] = useState(false);
  const [operations, setOperations] = useState<Operation[]>([]);
  const [counts, setCounts] = useState<Overview | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [runPages, setRunPages] = useState<Record<string, number>>({});
  const [selectedRunIdsByBaseline, setSelectedRunIdsByBaseline] = useState<Record<string, string[]>>({});
  const [classifications, setClassifications] = useState<string[]>([]);
  const [reviewStatuses, setReviewStatuses] = useState<string[]>([]);
  const runPage = runPages[baselineId] ?? 1;
  const selectedRunIds = selectedRunIdsByBaseline[baselineId] ?? [];
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<string | null>(null);
  const command = useRef<{ signature: string; key: string } | null>(null);
  const completed = useRef(new Set<string>());
  const imported = useRef(onImported);
  useEffect(() => { imported.current = onImported; }, [onImported]);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const rows = await api<Operation[]>(`${base}/operations?page=${page}`, { signal: controller.signal });
        setOperations(rows);
        for (const row of rows) {
          if (row.status === "succeeded" && !completed.current.has(row.id)) {
            completed.current.add(row.id);
            if (row.kind === "import") imported.current();
          }
        }
        if (rows.some(r => ["queued", "running"].includes(r.status))) timer = setTimeout(load, 3000);
      } catch (e) { if (!controller.signal.aborted) setError(message(e)); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [base, page, refresh]);
  useEffect(() => {
    if (!baselineId) return;
    const controller = new AbortController();
    Promise.all([
      api<Overview>(`${base}/overview?baseline_id=${baselineId}`, { signal: controller.signal }),
      api<Run[]>(`${base}/analysis?baseline_id=${baselineId}&page=${runPage}`, { signal: controller.signal }),
    ]).then(([overview, analysisRuns]) => { setCounts(overview); setRuns(analysisRuns); })
      .catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [base, baselineId, refresh, operations, refreshVersion, runPage]);
  async function send<T>(path: string, body: object): Promise<T> {
    const signature = path + JSON.stringify(body);
    if (command.current?.signature !== signature) command.current = { signature, key: crypto.randomUUID() };
    const result = await api<T>(base + path, { method: "POST", body: JSON.stringify(body),
      headers: { "Idempotency-Key": command.current.key } }, session.csrf_token);
    command.current = null;
    setRefresh(n => n + 1);
    return result;
  }
  async function action(work: () => Promise<void>) {
    setBusy(true); setError("");
    try { await work(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>CSV imports and reports</h2>
    {error && <p role="alert" className="alert">{error} <button onClick={() => { setError(""); setRefresh(n => n + 1); }}>Retry</button></p>}
    {canWrite && <form className="stack" onSubmit={event => { event.preventDefault(); void action(async () => {
      if (!file || file.size > 1_000_000) throw new Error("Choose a CSV up to 1 MB.");
      const csvText = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      setPreview(await send<Preview>("/imports/preview", { kind, csv_text: csvText, baseline_id: baselineId || null,
        column_mapping: Object.fromEntries(Object.entries(mapping).filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()])) }));
      setPartial(false);
    }); }}>
      <label>CSV kind<select value={kind} onChange={e => { setKind(e.target.value as "task" | "test"); setMapping({}); setPreview(null); }}><option value="task">Tasks</option><option value="test">Tests</option></select></label>
      <p>Task headers: external_id,title,description,status. Test headers: test_id,name,result,executed_at. Optional: environment,url,requirement_id. Use timezone-aware timestamps and at most 500 rows. Select a published baseline above to resolve requirement codes.</p>
      <label>CSV file<input type="file" accept=".csv,text/csv" required onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); }} /></label>
      <p><a href={`/templates/${kind === "task" ? "tasks" : "tests"}.csv`} download>Download {kind} CSV template</a>. Replace sample values with your evidence; clear requirement_id if you are not linking a published requirement.</p>
      <details><summary>Map custom CSV headers</summary><p>Enter the exact header from your file for each field you want to rename. Leave blank to use the standard header. Unsupported extra columns must be removed from the file.</p>
        {(kind === "task" ? ["external_id", "title", "description", "status", "url", "updated_at", "requirement_id", "related_requirement_id"] : ["test_id", "name", "result", "executed_at", "environment", "url", "updated_at", "requirement_id", "related_requirement_id"]).map(field => <label key={field}>CSV header for {field}<input value={mapping[field] ?? ""} maxLength={200} placeholder={field} onChange={e => {setMapping({...mapping, [field]:e.target.value}); setPreview(null);}} /></label>)}
      </details>
      <button className="primary" disabled={busy}>Preview CSV</button>
    </form>}
    {preview && <div><h3>Import preview</h3><p>{preview.rows.filter(row => !(row.errors ?? []).length).length} valid rows; {preview.rows.filter(row => (row.errors ?? []).length).length} rejected rows.</p>
      <div className="table-scroll"><table><thead><tr><th>CSV row</th><th>Normalized artifact</th><th>Validation</th></tr></thead><tbody>{preview.rows.map(row => <tr key={row.number}><td>{row.number}</td><td>{String(row.artifact?.external_id ?? "")} · {String(row.artifact?.title ?? "")}</td><td>{(row.errors ?? []).join("; ") || "Valid — links will be proposals"}</td></tr>)}</tbody></table></div>
      {canWrite && preview.status === "preview" && <><label><input type="checkbox" checked={partial} onChange={e => setPartial(e.target.checked)} /> Import valid rows even if some rows are rejected</label>
        <button disabled={busy} onClick={() => void action(async () => { const result = await send<Operation>(`/imports/${preview.id}/commit`, { accept_partial: partial }); setPreview({ ...preview, ...result }); })}>Confirm import</button></>}
    </div>}
    <h3>Baseline overview and frozen reports</h3>
    {!baselineId ? <p>Select a published baseline above.</p> : <>
      {counts?.baseline_id === baselineId && <p>{counts.requirements} requirements · {counts.accepted_current_evidence} with accepted current evidence · {counts.missing_current_evidence} without accepted current evidence · {counts.stale_links} stale links · {counts.pending_findings} pending finding proposals.</p>}
      <fieldset className="stack"><legend>Filter report findings</legend>
        <p>Leave runs unselected to include all runs for this baseline. Leave a finding filter empty to include every value.</p>
        <div className="table-scroll"><table><caption>Analysis runs in this baseline</caption><thead><tr><th>Select</th><th>Created</th><th>Provider</th><th>Finding proposals</th></tr></thead><tbody>
          {runs.map(run => <tr key={run.id}><td><label><input type="checkbox" checked={selectedRunIds.includes(run.id)} onChange={event => setSelectedRunIdsByBaseline(previous => {
            const current = previous[baselineId] ?? [];
            return { ...previous, [baselineId]: event.target.checked ? [...new Set([...current, run.id])] : current.filter(id => id !== run.id) };
          })} /> Include run</label></td><td>{new Date(run.created_at).toLocaleString()}</td><td>{run.provider}</td><td>{run.findings.length}</td></tr>)}
          {!runs.length && <tr><td colSpan={4}>No analysis runs for this baseline.</td></tr>}
        </tbody></table></div>
        <nav aria-label="Report run pages"><button type="button" disabled={runPage === 1} onClick={() => setRunPages(previous => ({ ...previous, [baselineId]: runPage - 1 }))}>Previous runs</button> Page {runPage} <button type="button" disabled={runs.length < 25} onClick={() => setRunPages(previous => ({ ...previous, [baselineId]: runPage + 1 }))}>Next runs</button></nav>
        <fieldset><legend>Finding classifications</legend>
          {["IN_SCOPE", "POTENTIAL_SCOPE_ADDITION", "CONFLICT", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE"].map(value => <label key={value}><input type="checkbox" checked={classifications.includes(value)} onChange={event => setClassifications(current => event.target.checked ? [...current, value] : current.filter(item => item !== value))} /> {value.replaceAll("_", " ")}</label>)}
        </fieldset>
        <fieldset><legend>Review states</legend>
          {["pending", "confirmed", "dismissed", "clarification_requested"].map(value => <label key={value}><input type="checkbox" checked={reviewStatuses.includes(value)} onChange={event => setReviewStatuses(current => event.target.checked ? [...current, value] : current.filter(item => item !== value))} /> {value.replaceAll("_", " ")}</label>)}
        </fieldset>
        {canWrite && <button className="primary" disabled={busy} onClick={() => void action(async () => {
          await send("/reports", {
            baseline_id: baselineId,
            run_ids: selectedRunIds.length ? selectedRunIds : null,
            classifications,
            review_statuses: reviewStatuses,
          });
        })}>Generate frozen report</button>}
      </fieldset>
    </>}
    <h3>Recent jobs</h3>
    {!operations.length && <p>No imports or reports on this page.</p>}
    {operations.map(op => <div key={op.id}><p>{op.kind} · {op.status} · {new Date(op.created_at).toLocaleString()}</p>
      {op.status === "queued" && <p role="status">Queued for the background worker. This page updates automatically.</p>}
      {op.error && <p role="alert">{op.error}</p>}
      {op.kind === "import" && <button onClick={() => void action(async () => setPreview(await api<Preview>(`${base}/operations/${op.id}`)))}>Inspect import</button>}
      {op.result && op.kind === "import" && <p>Accepted: {String(op.result.accepted)}; rejected: {String(op.result.rejected)}; changed: {String(op.result.changed)}; unchanged: {String(op.result.unchanged)}.</p>}
      {typeof op.result?.report_id === "string" && <div>
        <button onClick={() => void action(async () => { const response = await fetch(`/api/v1${base}/reports/${op.result?.report_id}/download?format=md`, { cache: "no-store", credentials: "same-origin" }); if (!response.ok) throw new Error("Report unavailable. Sign in again if your session expired."); setReport(await response.text()); })}>Preview snapshot</button>{" "}
        <a href={`/api/v1${base}/reports/${op.result.report_id}/download?format=md`}>Download Markdown</a>{" · "}
        <a href={`/api/v1${base}/reports/${op.result.report_id}/download?format=csv`}>Download CSV</a>
      </div>}
    </div>)}
    <nav aria-label="Import and report pages"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous jobs</button> Page {page} <button disabled={operations.length < 25} onClick={() => setPage(p => p + 1)}>Next jobs</button></nav>
    {report && <details open><summary>Frozen report preview</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{report}</pre></details>}
  </section>;
}
