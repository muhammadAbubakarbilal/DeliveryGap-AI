"use client";
import { useEffect, useRef, useState } from "react";
import { api, message } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "./shell";

type Documents = components["schemas"]["DocumentPage"];
type Operation = components["schemas"]["OperationOut"];
export function RequirementExtraction({ projectId, canWrite, canCancel, externalAiConsent, onComplete }: {
  projectId: string; canWrite: boolean; canCancel: boolean; externalAiConsent: boolean; onComplete: () => void;
}) {
  const session = useSession();
  const [documents, setDocuments] = useState<Documents | null>(null);
  const [page, setPage] = useState(1);
  const [version, setVersion] = useState("");
  const [operations, setOperations] = useState<Operation[]>([]);
  const [jobPage, setJobPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const key = useRef<{version: string; value: string} | null>(null);
  const retryKeys = useRef(new Map<string, string>());
  const seen = useRef(new Set<string>());
  const complete = useRef(onComplete);
  useEffect(() => { complete.current = onComplete; }, [onComplete]);
  const base = `/projects/${projectId}`;
  useEffect(() => {
    const controller = new AbortController();
    api<Documents>(`${base}/documents?page=${page}`, { signal: controller.signal }).then(setDocuments)
      .catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [base, page, refresh]);
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const rows = await api<Operation[]>(`${base}/operations?page=${jobPage}&kind=extraction`, { signal: controller.signal });
        setOperations(rows);
        for (const row of rows) if (row.status === "succeeded" && !seen.current.has(row.id)) { seen.current.add(row.id); complete.current(); }
        if (rows.some(row => ["queued", "running"].includes(row.status))) timer = setTimeout(load, 3000);
      } catch(e) { if (!controller.signal.aborted) setError(message(e)); }
    }
    void load(); return () => { controller.abort(); clearTimeout(timer); };
  }, [base, jobPage, refresh]);
  return <section className="panel"><h2>Extract requirement drafts</h2><p>Extract source-backed proposals for human review. This sends the selected source to the configured model provider. No requirement is approved automatically.</p>
    {!externalAiConsent && <p role="status">A project lead must enable external AI processing in project settings before extraction can be queued.</p>}
    {error && <p role="alert">{error} <button onClick={() => {setError(""); setRefresh(n => n + 1);}}>Refresh extraction</button></p>}
    {canWrite && <form className="stack" onSubmit={event => { event.preventDefault(); setBusy(true); setError("");
      if (key.current?.version !== version) key.current = {version, value:crypto.randomUUID()};
      void api<Operation>(`${base}/requirements/extract`, { method: "POST", body: JSON.stringify({source_version_id:version}), headers:{"Idempotency-Key":key.current.value}}, session.csrf_token)
        .then(() => { key.current = null; setJobPage(1); setRefresh(n => n + 1); }).catch(e => setError(message(e))).finally(() => setBusy(false));
    }}><label>Source for extraction<select required value={version} onChange={e => setVersion(e.target.value)}><option value="">Select a ready source</option>{documents?.items.flatMap(d => d.versions.filter(v => v.status === "ready").map(v => <option key={v.id} value={v.id}>{d.title} · v{v.version_number}</option>))}</select></label>
      <div><button type="button" disabled={page === 1} onClick={() => {setPage(p => p - 1);setVersion("");}}>Earlier sources</button><button type="button" disabled={!documents || page * 25 >= documents.total} onClick={() => {setPage(p => p + 1);setVersion("");}}>More sources</button></div>
      <p>Up to 32 batches, with 20 proposals per batch. Progress is saved between batches; drafts appear after every batch passes validation.</p><button className="primary" disabled={busy || !version || !externalAiConsent}>Extract drafts</button></form>}
    {!operations.length && <p>No extraction jobs on this page.</p>}
    {operations.map(op => <div key={op.id}><p>Extraction · {op.status} · {new Date(op.created_at).toLocaleString()}</p>{op.error && <p role="alert">{op.error}</p>}{op.status === "succeeded" && <p role="status">{String(op.result?.drafts_created ?? 0)} drafts saved for review.</p>}{["queued", "running"].includes(op.status) && <p role="status">{String(op.result?.batches_completed ?? 0)} batches completed. Waiting for background processing.</p>}
      {canWrite && op.status === "failed" && <button disabled={busy || !externalAiConsent || op.attempts >= 3} onClick={() => {
        const retryKey = retryKeys.current.get(op.id) ?? crypto.randomUUID();
        retryKeys.current.set(op.id, retryKey);
        setBusy(true); setError("");
        void api<Operation>(`${base}/operations/${op.id}/retry`, {method:"POST", body:"{}", headers:{"Idempotency-Key":retryKey}}, session.csrf_token)
          .then(() => {retryKeys.current.delete(op.id); setRefresh(n => n + 1);})
          .catch(e => setError(message(e))).finally(() => setBusy(false));
      }}>Retry failed extraction</button>}
      {op.status === "failed" && op.attempts >= 3 && <p role="status">Retry limit reached. Start a new extraction after checking the provider or source.</p>}
      {canCancel && ["queued", "running"].includes(op.status) && <button disabled={busy} onClick={() => {setBusy(true); void api(`${base}/operations/${op.id}/cancel`, {method:"POST"}, session.csrf_token).then(() => setRefresh(n => n + 1)).catch(e => setError(message(e))).finally(() => setBusy(false));}}>Cancel extraction</button>}</div>)}
    <nav aria-label="Extraction job pages"><button disabled={jobPage === 1} onClick={() => setJobPage(p => p - 1)}>Previous extractions</button> Page {jobPage} <button disabled={operations.length < 25} onClick={() => setJobPage(p => p + 1)}>Next extractions</button></nav>
  </section>;
}
