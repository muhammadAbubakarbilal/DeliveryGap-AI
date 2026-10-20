"use client";

import { useEffect, useState } from "react";
import { api, message } from "@/lib/api";
import type { components } from "@/lib/api-types";

type DocumentPage = components["schemas"]["DocumentPage"];
type SpanPage = components["schemas"]["SpanPage"];
type Version = components["schemas"]["RequirementVersionOut"];

export function RequirementEvidencePicker({ projectId, initial, namePrefix = "" }: {
  projectId: string; initial?: Version; namePrefix?: string;
}) {
  const [documents, setDocuments] = useState<DocumentPage | null>(null);
  const [spans, setSpans] = useState<SpanPage | null>(null);
  const [documentPage, setDocumentPage] = useState(1);
  const [spanPage, setSpanPage] = useState(1);
  const [versionId, setVersionId] = useState(initial?.source_version_id ?? "");
  const [spanId, setSpanId] = useState(initial?.source_span_id ?? "");
  const [quote, setQuote] = useState(initial?.source_quote ?? "");
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api<DocumentPage>(`/projects/${projectId}/documents?page=${documentPage}`, { signal: controller.signal })
      .then(setDocuments).catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [projectId, documentPage]);
  useEffect(() => {
    if (!versionId) return;
    const controller = new AbortController();
    api<SpanPage>(`/projects/${projectId}/versions/${versionId}/spans?page=${spanPage}`, { signal: controller.signal })
      .then(setSpans).catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [projectId, versionId, spanPage]);
  return <fieldset className="stack"><legend>Source evidence</legend>
    {error && <p role="alert">{error}</p>}
    <label>Document version<select name={`${namePrefix}source_version_id`} value={versionId} onChange={e => { setVersionId(e.target.value); setSpanId(""); setQuote(""); setSpans(null); setSpanPage(1); setError(""); }}>
      <option value="">Save without evidence</option>
      {versionId && !documents?.items.some(d => d.versions.some(v => v.id === versionId)) && <option value={versionId}>Current cited version</option>}
      {documents?.items.flatMap(d => d.versions.filter(v => v.status === "ready").map(v => <option key={v.id} value={v.id}>{d.title} · v{v.version_number}</option>))}
    </select></label>
    <div><button type="button" disabled={documentPage === 1} onClick={() => setDocumentPage(p => p - 1)}>Previous documents</button> Page {documentPage} <button type="button" disabled={!documents || documentPage * 25 >= documents.total} onClick={() => setDocumentPage(p => p + 1)}>Next documents</button></div>
    {versionId && <>
      <label>Source passage<select name={`${namePrefix}source_span_id`} required value={spanId} onChange={e => { setSpanId(e.target.value); setQuote(spans?.items.find(s => s.id === e.target.value)?.text.slice(0, 20000) ?? ""); }}>
        <option value="">Choose a passage</option>
        {spanId && !spans?.items.some(s => s.id === spanId) && <option value={spanId}>Current cited passage</option>}
        {spans?.items.map(s => <option key={s.id} value={s.id}>{s.locator} · {s.text.slice(0, 100)}</option>)}
      </select></label>
      <div><button type="button" disabled={spanPage === 1} onClick={() => setSpanPage(p => p - 1)}>Previous passages</button> Page {spanPage} <button type="button" disabled={!spans || spanPage * 25 >= spans.total} onClick={() => setSpanPage(p => p + 1)}>Next passages</button></div>
      <label>Exact quote<textarea name={`${namePrefix}source_quote`} required maxLength={20000} value={quote} onChange={e => setQuote(e.target.value)} /></label>
      <p>Select the exact portion that supports this requirement. The server checks it against the original passage.</p>
    </>}
  </fieldset>;
}
