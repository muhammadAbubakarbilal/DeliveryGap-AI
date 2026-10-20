"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, message, type Project } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "@/components/shell";

type Document = components["schemas"]["DocumentOut"];
type Documents = components["schemas"]["DocumentPage"];
type Spans = components["schemas"]["SpanPage"];
type Job = components["schemas"]["JobOut"];
type Upload = components["schemas"]["UploadOut"];

export function SourceWorkspace({ projectId, documentId }: { projectId: string; documentId?: string }) {
  const session = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<Documents | null>(null);
  const [document, setDocument] = useState<Document | null>(null);
  const [versionId, setVersionId] = useState("");
  const [spans, setSpans] = useState<Spans | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [manual, setManual] = useState(false);
  const keys = useRef(new Map<string, string>());
  const pending = useRef(false);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const base = `/projects/${projectId}`;
  const version = document?.versions.find(v => v.id === versionId) ?? document?.versions[0];
  const canWrite = project?.status === "active" && (session.user.is_admin || project?.role === "lead" || project?.role === "member");
  useEffect(() => () => xhrRef.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const p = await api<Project>(base, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setProject(p);
        let active = false;
        if (documentId) {
          const d = await api<Document>(`${base}/documents/${documentId}`, { signal: controller.signal });
          const selected = d.versions.find(v => v.id === versionId) ?? d.versions[0];
          const [s, j] = await Promise.all([
            api<Spans>(`${base}/versions/${selected.id}/spans?page=${page}`, { signal: controller.signal }),
            api<Job>(`${base}/versions/${selected.id}/job`, { signal: controller.signal }),
          ]);
          if (controller.signal.aborted) return;
          setDocument(d); setSpans(s); setJob(j);
          active = ["queued", "running"].includes(j.status);
        } else {
          const d = await api<Documents>(`${base}/documents?page=${page}`, { signal: controller.signal });
          if (controller.signal.aborted) return;
          setDocuments(d);
          active = d.items.some(item => item.versions.some(v => ["queued", "processing"].includes(v.status)));
        }
        if (active) timer = setTimeout(load, 2500);
      } catch (e) {
        if (!controller.signal.aborted) setError(message(e));
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [base, documentId, page, reload, versionId]);

  function keyFor(body: string) {
    const key = keys.current.get(body) ?? crypto.randomUUID();
    keys.current.set(body, key);
    return key;
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(""); setNotice(""); setProgress(0);
    const element = event.currentTarget;
    const fields = new FormData(element);
    const title = String(fields.get("title") ?? "").trim();
    const kind = String(fields.get("kind") ?? "scope");
    try {
      let result: Upload;
      if (manual) {
        const body = JSON.stringify({ title, kind, text: String(fields.get("text") ?? "") });
        result = await api<Upload>(`${base}/documents/manual${documentId ? `?document_id=${documentId}` : ""}`, {
          method: "POST", body, headers: { "Idempotency-Key": keyFor(body) },
        }, session.csrf_token);
      } else {
        const file = fields.get("file");
        if (!(file instanceof File) || file.size === 0) throw new Error("Select a non-empty file.");
        if (file.size > 10 * 1024 * 1024) throw new Error("Files must be at most 10 MB.");
        const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer())), n => n.toString(16).padStart(2, "0")).join("");
        const key = keyFor(JSON.stringify([title, kind, file.name, file.type, hash]));
        const params = new URLSearchParams({ title, kind, filename: file.name });
        if (documentId) params.set("document_id", documentId);
        result = await new Promise<Upload>((resolve, reject) => {
          const xhr = new XMLHttpRequest(); xhrRef.current = xhr;
          xhr.open("POST", `/api/v1${base}/documents?${params}`);
          xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
          xhr.setRequestHeader("X-CSRF-Token", session.csrf_token);
          xhr.setRequestHeader("Idempotency-Key", key);
          xhr.timeout = 120000;
          xhr.upload.onprogress = e => { if (e.lengthComputable) setProgress(Math.round(100 * e.loaded / e.total)); };
          xhr.onerror = xhr.ontimeout = () => reject(new Error("Upload interrupted. Retry with the same file."));
          xhr.onabort = () => reject(new Error("Upload cancelled."));
          xhr.onload = () => {
            if (xhr.status === 401) window.location.replace("/login");
            try {
              const body = JSON.parse(xhr.responseText);
              if (xhr.status >= 200 && xhr.status < 300) resolve(body);
              else reject(new Error(body.error?.message ?? "Upload failed. Retry with the same file."));
            } catch { reject(new Error("Invalid upload response. Retry with the same file.")); }
          };
          xhr.send(file);
        });
      }
      keys.current.clear(); element.reset();
      setNotice(result.duplicate ? "Uploaded. Identical content already exists in this project; the new version is preserved." : "Uploaded privately. Parsing is queued.");
      setVersionId(result.version_id); setPage(1); setSpans(null); setReload(n => n + 1);
    } catch (e) { setError(message(e)); }
    finally { pending.current = false; setBusy(false); xhrRef.current = null; }
  }
  async function retry() {
    if (!version || pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      await api(`${base}/versions/${version.id}/retry`, { method: "POST", headers: { "Idempotency-Key": keyFor(`retry:${version.id}:${job?.attempts[0]?.number}`) } }, session.csrf_token);
      setReload(n => n + 1);
    } catch (e) { setError(message(e)); }
    finally { pending.current = false; setBusy(false); }
  }
  return <>
    <Link className="back-link" href={documentId ? `${base}/documents` : base}>{documentId ? "All documents" : "Back to project"}</Link>
    <div className="page-heading"><div><div className="eyebrow">PROJECT SOURCES</div><h1>{document?.title ?? "Documents"}</h1><p>Private originals and traceable source text. Parsing does not extract or approve requirements.</p></div></div>
    {error && <div className="alert" role="alert">{error} <button onClick={() => { setError(""); setReload(n => n + 1); }}>Refresh</button></div>}
    {notice && <div className="success" role="status">{notice}</div>}
    {!project && !error && <p role="status">Loading sources…</p>}
    {project && !canWrite && <p className="subtle">You can view and download sources. Uploading requires an active project and contributor access.</p>}
    {canWrite && <section className="panel source-upload"><h2>{documentId ? "Add a new version" : "Add a document"}</h2>
      <p className="subtle">PDF, DOCX, UTF-8 TXT or Markdown · up to 10 MB. Originals are never replaced.</p>
      <label className="source-toggle"><input type="checkbox" checked={manual} disabled={busy} onChange={e => setManual(e.target.checked)} /> Enter manual text instead</label>
      <form onSubmit={submit}><fieldset disabled={busy}><div className="form-grid">
        <label>Document title<input name="title" required maxLength={200} defaultValue={document?.title ?? ""} /></label>
        <label>Document purpose<select name="kind" defaultValue={document?.kind ?? "scope"}><option value="scope">Scope</option><option value="change_request">Change request</option><option value="meeting_notes">Meeting notes</option><option value="other">Other</option></select></label>
      </div>{manual ? <label>Manually authored text<textarea name="text" required maxLength={100000} rows={8} /><small>Saved as a separate, explicitly labeled source version. It does not claim to be an exact extraction of the original.</small></label> : <label className="source-drop" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); const input = e.currentTarget.querySelector("input"); if (input && !busy) input.files = e.dataTransfer.files; }}>Source file<input name="file" type="file" accept=".pdf,.docx,.txt,.md" required /><small>Choose a file or drop it here.</small></label>}
      <button className="primary" type="submit">{busy ? "Uploading…" : manual ? "Save manual source" : "Upload source"}</button></fieldset></form>
      {busy && <div role="status"><progress max={100} value={progress} aria-label="Upload progress" /> {progress}% transferred; waiting for confirmation.</div>}
    </section>}
    {!documentId && documents && <section className="panel"><h2>Document library</h2>{documents.items.length === 0 ? <p className="subtle">No documents yet. Add a source to begin.</p> : <ul className="source-list">{documents.items.map(d => <li key={d.id}><Link href={`${base}/documents/${d.id}`}>{d.title}</Link><span>{d.kind.replaceAll("_", " ")} · Version {d.versions[0].version_number} · {d.versions[0].status.replaceAll("_", " ")}</span></li>)}</ul>}
      <div className="pagination"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page}</span><button disabled={page * 25 >= documents.total} onClick={() => setPage(p => p + 1)}>Next</button></div>
    </section>}
    {document && version && <section className="panel"><div className="section-heading"><h2>Source viewer</h2><label>Version<select value={version.id} onChange={e => { setVersionId(e.target.value); setPage(1); setSpans(null); }}>{document.versions.map(v => <option key={v.id} value={v.id}>{v.version_number} · {v.filename}{v.is_manual ? " · Manually authored" : ""}</option>)}</select></label></div>
      <p className="subtle">{version.status.replaceAll("_", " ")} · {version.byte_size} bytes{version.is_manual && " · Manually authored source"}</p>
      <a className="back-link" href={`/api/v1${base}/versions/${version.id}/download`}>Download original</a>
      {version.warning && <p className="alert" role="status">{version.warning}</p>}
      {job?.error && <p className="alert" role="status">{job.error}</p>}
      {job?.status === "failed" && canWrite && <button disabled={busy} onClick={retry}>Retry parsing</button>}
      {["queued", "processing"].includes(version.status) && <p role="status">Parsing is {version.status}. This page updates automatically.</p>}
      {spans?.items.map(span => <article className="source-span" id={`span-${span.id}`} key={span.id}><h3><a href={`#span-${span.id}`}>{span.locator}</a></h3><small>Characters {span.char_start}–{span.char_end} within this source location</small><pre>{span.text || "No text at this location."}</pre></article>)}
      {spans && spans.total > 25 && <div className="pagination"><button disabled={page === 1} onClick={() => { setSpans(null); setPage(p => p - 1); }}>Previous locations</button><span>Page {page}</span><button disabled={page * 25 >= spans.total} onClick={() => { setSpans(null); setPage(p => p + 1); }}>Next locations</button></div>}
      {job && <details><summary>Processing attempts ({job.attempts.length})</summary><ul>{job.attempts.map(a => <li key={a.number}>Attempt {a.number}: {a.status}</li>)}</ul></details>}
    </section>}
  </>;
}
