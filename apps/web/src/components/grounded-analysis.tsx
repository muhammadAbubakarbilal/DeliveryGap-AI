"use client";
import { useEffect, useRef, useState } from "react";
import { api, message } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "./shell";

type Operation = components["schemas"]["OperationOut"];
type Baseline = components["schemas"]["BaselineOut"];
type RetrievalCandidate = {
  id: string;
  title: string;
  source_quote: string;
  lexical_rank: number | null;
  semantic_rank: number | null;
  fused_rank: number;
};

type RequestSegment = {
  request_index: number;
  start: number;
  end: number;
  text: string;
  status: string;
  error?: string;
  candidates: RetrievalCandidate[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCandidate(row: unknown): row is RetrievalCandidate {
    if (!isRecord(row)) return false;
    const candidate = row;
    return typeof candidate.id === "string"
      && typeof candidate.title === "string"
      && typeof candidate.source_quote === "string"
      && typeof candidate.fused_rank === "number"
      && (typeof candidate.lexical_rank === "number" || candidate.lexical_rank === null)
      && (typeof candidate.semantic_rank === "number" || candidate.semantic_rank === null);
}

function requestSegments(result: Operation["result"]): RequestSegment[] {
  const rows = result?.request_segments;
  if (!Array.isArray(rows)) return [];
  return rows.flatMap((row): RequestSegment[] => {
    if (!isRecord(row) || !Array.isArray(row.candidates)) return [];
    const candidates = row.candidates.filter(isCandidate);
    if (typeof row.request_index !== "number" || typeof row.start !== "number"
      || typeof row.end !== "number" || typeof row.text !== "string"
      || typeof row.status !== "string") return [];
    return [{
      request_index: row.request_index,
      start: row.start,
      end: row.end,
      text: row.text,
      status: row.status,
      error: typeof row.error === "string" ? row.error : undefined,
      candidates,
    }];
  });
}

export function GroundedAnalysis({ projectId, baselines, canWrite, canCancel, externalAiConsent, onComplete }: {
  projectId: string; baselines: Baseline[]; canWrite: boolean; canCancel: boolean; externalAiConsent: boolean; onComplete: () => void;
}) {
  const session = useSession();
  const base = `/projects/${projectId}`;
  const [jobs, setJobs] = useState<Operation[]>([]);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const key = useRef<{payload: string; value: string} | null>(null);
  const retryKeys = useRef(new Map<string, string>());
  const seen = useRef(new Set<string>());
  const complete = useRef(onComplete);
  useEffect(() => { complete.current = onComplete; }, [onComplete]);
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const rows = await api<Operation[]>(`${base}/operations?kind=analysis&page=${page}`, {signal:controller.signal});
        setJobs(rows);
        for (const row of rows) if (row.status === "succeeded" && !seen.current.has(row.id)) {
          seen.current.add(row.id); complete.current();
        }
        if (rows.some(row => ["queued", "running"].includes(row.status))) timer = setTimeout(load, 3000);
      } catch(e) { if (!controller.signal.aborted) setError(message(e)); }
    }
    void load(); return () => { controller.abort(); clearTimeout(timer); };
  }, [base, page, refresh]);
  return <section className="panel"><h2>Analyze a change request</h2>
    <p>Each change request is decomposed into at most 10 exact, non-overlapping action spans, then compared with a published baseline using BM25 and semantic retrieval. The configured model receives each span and up to five approved passages. Retrieval ranks are not confidence scores, and findings require human review.</p>
    <p>Model quality has not been evaluated on human-reviewed held-out data. No retrieved evidence does not prove missing scope or implementation.</p>
    {!externalAiConsent && <p role="status">A project lead must enable external AI processing in project settings before analysis can be queued.</p>}
    <p>Requires the background worker and an enabled AI provider. No match produces an insufficient-evidence result.</p>
    {error && <p role="alert">{error} <button onClick={() => {setError(""); setRefresh(n => n + 1);}}>Refresh analysis jobs</button></p>}
    {canWrite && <form className="stack" onSubmit={event => {
      event.preventDefault(); const form = new FormData(event.currentTarget);
      const payload = JSON.stringify({baseline_id:form.get("baseline"), input_text:form.get("request")});
      if (key.current?.payload !== payload) key.current = {payload, value:crypto.randomUUID()};
      setBusy(true); setError("");
      void api(`${base}/analysis-jobs`, {method:"POST", body:payload, headers:{"Idempotency-Key":key.current.value}}, session.csrf_token)
        .then(() => {key.current = null; setPage(1); setRefresh(n => n + 1);})
        .catch(e => setError(message(e))).finally(() => setBusy(false));
    }}><label>Analysis baseline<select name="baseline" required><option value="">Choose a published baseline</option>{baselines.map(b => <option key={b.id} value={b.id}>B{b.number}</option>)}</select></label>
      <label>Change request<textarea name="request" required maxLength={4000} rows={4}/></label>
      <button className="primary" disabled={busy || !baselines.length || !externalAiConsent}>Queue change analysis</button></form>}
    {!jobs.length && <p>No analysis jobs on this page.</p>}
    {jobs.map(job => <div key={job.id}><p>Analysis · {job.status} · {new Date(job.created_at).toLocaleString()}</p>
      {job.error && <p role="alert">{job.error}</p>}
      {job.status === "succeeded" && isRecord(job.result) && typeof job.result.message === "string"
        && <p role="status">{job.result.message}</p>}
      {job.status === "succeeded" && requestSegments(job.result).map(segment => <div key={segment.request_index}>
        <h3>Request {segment.request_index + 1} · {segment.status}</h3>
        <p>Source characters {segment.start}–{segment.end} (zero-based Unicode code-point offsets; end is exclusive).</p>
        <blockquote>{segment.text}</blockquote>
        {segment.error && <p role="alert">{segment.error}</p>}
        {segment.candidates.length > 0 && <>
          <h4>Retrieved baseline candidates</h4>
          <p>Ranks explain retrieval order only; they are not confidence values.</p>
          <ol>{segment.candidates.map(candidate => <li key={candidate.id}>
            <strong>{candidate.title}</strong> · fused rank {candidate.fused_rank}; lexical rank {candidate.lexical_rank ?? "not ranked"}; semantic rank {candidate.semantic_rank ?? "not ranked"}
            {candidate.source_quote && <blockquote>{candidate.source_quote}</blockquote>}
          </li>)}</ol>
        </>}
      </div>)}
      {canWrite && job.status === "failed" && <button disabled={busy || !externalAiConsent || job.attempts >= 3} onClick={() => {
        const retryKey = retryKeys.current.get(job.id) ?? crypto.randomUUID();
        retryKeys.current.set(job.id, retryKey);
        setBusy(true); setError("");
        void api<Operation>(`${base}/operations/${job.id}/retry`, {method:"POST", body:"{}", headers:{"Idempotency-Key":retryKey}}, session.csrf_token)
          .then(() => {retryKeys.current.delete(job.id); setRefresh(n => n + 1);})
          .catch(e => setError(message(e))).finally(() => setBusy(false));
      }}>Retry failed analysis</button>}
      {job.status === "failed" && job.attempts >= 3 && <p role="status">Retry limit reached. Start a new analysis after checking the provider or baseline.</p>}
      {canCancel && ["queued", "running"].includes(job.status) && <button disabled={busy} onClick={() => {
        setBusy(true); void api(`${base}/operations/${job.id}/cancel`, {method:"POST"}, session.csrf_token)
          .then(() => setRefresh(n => n + 1)).catch(e => setError(message(e))).finally(() => setBusy(false));
      }}>Cancel analysis</button>}</div>)}
    <nav aria-label="Analysis job pages"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous jobs</button> Page {page} <button disabled={jobs.length < 25} onClick={() => setPage(p => p + 1)}>Next jobs</button></nav>
  </section>;
}
