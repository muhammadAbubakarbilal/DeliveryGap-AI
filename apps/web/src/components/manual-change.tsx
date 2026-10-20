"use client";
import { useEffect, useRef, useState } from "react";
import { api, message } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "./shell";

type Baseline = components["schemas"]["BaselineOut"];
type Citation = components["schemas"]["BaselineCitation"];
type Input = components["schemas"]["ManualAnalysisCreate"];
const classes: Input["classification"][] = ["IN_SCOPE", "CONFLICT", "POTENTIAL_SCOPE_ADDITION", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE"];

export function ManualChange({projectId, baselines, canWrite, onSaved}: {
  projectId: string; baselines: Baseline[]; canWrite: boolean; onSaved: () => void;
}) {
  const session = useSession();
  const [baseline, setBaseline] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [selected, setSelected] = useState("");
  const [classification, setClassification] = useState<Input["classification"]>("INSUFFICIENT_EVIDENCE");
  const [quote, setQuote] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const key = useRef<{payload: string; key: string} | null>(null);
  const source = citations.find(c => c.requirement_version_id === selected);
  const required = ["IN_SCOPE", "CONFLICT", "POTENTIAL_SCOPE_ADDITION"].includes(classification);
  useEffect(() => {
    if (!baseline) return;
    const controller = new AbortController();
    api<Citation[]>(`/projects/${projectId}/baselines/${baseline}/citations`, {signal:controller.signal})
      .then(setCitations).catch(e => {if (!controller.signal.aborted) setError(message(e));})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [projectId, baseline, retry]);
  return <section className="panel"><h2>Record a manual change proposal</h2>
    <p>No AI is required. Record your comparison with approved scope, cite evidence, and ask a lead to confirm, dismiss, or request clarification. Missing evidence is not proof of missing implementation.</p>
    {error && <p role="alert">{error} <button onClick={() => {setError(""); setLoading(Boolean(baseline)); setRetry(n => n + 1);}}>Refresh source evidence</button></p>}
    {notice && <p role="status">{notice}</p>}
    {!canWrite ? <p>Contributor access to an active project is required to submit proposals.</p> : <form className="stack" onSubmit={event => {
      event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
      const body: Input = {baseline_id:baseline, input_text:String(data.get("request")), classification,
        summary:String(data.get("rationale")), requirement_version_id:selected || null, evidence_quote:quote || null};
      const payload = JSON.stringify(body);
      if (key.current?.payload !== payload) key.current = {payload, key:crypto.randomUUID()};
      setBusy(true); setError(""); setNotice("");
      void api(`/projects/${projectId}/manual-analysis`, {method:"POST", body:payload, headers:{"Idempotency-Key":key.current.key}}, session.csrf_token)
        .then(() => {key.current = null; form.reset(); setNotice("Manual proposal saved for lead review."); onSaved();})
        .catch(e => setError(message(e))).finally(() => setBusy(false));
    }}><label>Proposal baseline<select required value={baseline} onChange={e => {
      setBaseline(e.target.value); setSelected(""); setQuote(""); setCitations([]); setError(""); setLoading(Boolean(e.target.value));
    }}><option value="">Choose a published baseline</option>{baselines.map(b => <option key={b.id} value={b.id}>B{b.number}</option>)}</select></label>
      <label>Requested change<textarea name="request" required maxLength={20000} rows={3}/></label>
      <label>Proposed classification<select value={classification} onChange={e => setClassification(e.target.value as Input["classification"])}>{classes.map(c => <option key={c} value={c}>{c.replaceAll("_", " ")}</option>)}</select></label>
      <p>Conflict needs an explicit incompatible condition. A potential addition needs a concrete extension and must acknowledge that other provisions may cover it.</p>
      {loading && <p role="status">Loading baseline evidence…</p>}
      <label>Cited approved requirement<select required={required} disabled={!baseline || loading} value={selected} onChange={e => {
        setSelected(e.target.value); setQuote(citations.find(c => c.requirement_version_id === e.target.value)?.source_quote ?? "");
      }}><option value="">No supporting evidence</option>{citations.map(c => <option key={c.requirement_version_id} value={c.requirement_version_id}>{c.requirement_code} · {c.title}</option>)}</select></label>
      {source && <><h3>Approved requirement</h3><p>{source.content}</p><h3>Original source quote</h3><blockquote>{source.source_quote || "No source quote available."}</blockquote></>}
      <label>Exact supporting quote<textarea value={quote} onChange={e => setQuote(e.target.value)} required={required || Boolean(selected)} maxLength={20000} rows={3}/></label>
      <label>Reasoning for this proposal<textarea name="rationale" required maxLength={4000} rows={3}/></label>
      <button className="primary" disabled={busy || loading || !baseline}>Save manual proposal</button>
    </form>}
  </section>;
}
