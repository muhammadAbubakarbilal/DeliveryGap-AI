"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, message, type Project } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { useSession } from "@/components/shell";
import { RequirementEvidencePicker } from "@/components/requirement-evidence-picker";
import { RequirementExtraction } from "@/components/requirement-extraction";

type Requirement = components["schemas"]["RequirementOut"];
type Page = components["schemas"]["RequirementPage"];
type Baseline = components["schemas"]["BaselineOut"];

export function RequirementsWorkspace({ projectId }: { projectId: string }) {
  const session = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [requirements, setRequirements] = useState<Page | null>(null);
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [page, setPage] = useState(1);
  const [baselinePage, setBaselinePage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Requirement | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [mergeSelected, setMergeSelected] = useState<Record<string, Requirement>>({});
  const [transformAction, setTransformAction] = useState<"split" | "merge" | null>(null);
  const [transformParents, setTransformParents] = useState<Requirement[]>([]);
  const [childCount, setChildCount] = useState(2);
  const command = useRef<{ signature: string; key: string } | null>(null);
  const base = `/projects/${projectId}`;
  const canWrite = project?.status === "active" && (session.user.is_admin || project.role === "lead" || project.role === "member");
  const canReview = canWrite && (session.user.is_admin || project?.role === "lead");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<Project>(base, { signal: controller.signal }),
      api<Page>(`${base}/requirements?page=${page}`, { signal: controller.signal }),
      api<Baseline[]>(`${base}/baselines?page=${baselinePage}`, { signal: controller.signal }),
    ]).then(([p, r, b]) => { setProject(p); setRequirements(r); setBaselines(b); })
      .catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [base, page, baselinePage, refresh]);

  async function mutate(path: string, body: object, success: string, retryable = false) {
    setBusy(true); setError(""); setNotice("");
    const payload = JSON.stringify(body);
    const signature = path + payload;
    if (command.current?.signature !== signature) command.current = { signature, key: crypto.randomUUID() };
    try {
      await api(path, { method: "POST", body: payload, headers: retryable ? { "Idempotency-Key": command.current.key } : {} }, session.csrf_token);
      command.current = null;
      setNotice(success); setRefresh(n => n + 1);
      return true;
    } catch (e) { setError(message(e)); return false; }
    finally { setBusy(false); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = {
      title: String(form.get("title")), content: String(form.get("content")),
      source_version_id: String(form.get("source_version_id") || "") || null,
      source_span_id: String(form.get("source_span_id") || "") || null,
      source_quote: String(form.get("source_quote") || "") || null,
      ...(editing ? { expected_version: editing.current_version } : {}),
    };
    if (await mutate(editing ? `${base}/requirements/${editing.id}/versions` : `${base}/requirements`, body, "Draft saved for review.", true)) {
      setShowForm(false); setEditing(null);
    }
  }
  async function saveTransform(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!transformAction) return;
    const form = new FormData(event.currentTarget);
    const children = Array.from({ length: childCount }, (_, index) => {
      const prefix = `child_${index}_`;
      return {
        title: String(form.get(`${prefix}title`) ?? ""),
        content: String(form.get(`${prefix}content`) ?? ""),
        source_version_id: String(form.get(`${prefix}source_version_id`) || "") || null,
        source_span_id: String(form.get(`${prefix}source_span_id`) || "") || null,
        source_quote: String(form.get(`${prefix}source_quote`) || "") || null,
      };
    });
    const body = {
      action: transformAction,
      parents: transformParents.map(parent => ({
        requirement_id: parent.id,
        expected_version: parent.current_version,
      })),
      children,
    };
    const parentIds = transformParents.map(parent => parent.id);
    if (await mutate(
      `${base}/requirements/transform`,
      body,
      transformAction === "split" ? "Requirement split into source-grounded drafts." : "Requirements merged into a source-grounded draft.",
      true,
    )) {
      setSelected(previous => Object.fromEntries(Object.entries(previous).filter(([id]) => !parentIds.includes(id))));
      setMergeSelected({});
      setTransformAction(null);
      setTransformParents([]);
      setRefresh(n => n + 1);
    }
  }
  const current = editing?.versions.find(v => v.version_number === editing.current_version);
  return <>
    <Link className="back-link" href={`/projects/${projectId}`}>Back to project</Link>
    <div className="page-heading"><div><div className="eyebrow">APPROVED SCOPE</div><h1>{project?.name ?? "Requirements"}</h1><p>Review source-backed proposals and select approved revisions for a baseline.</p></div>
      {canWrite && <button className="primary" disabled={busy} onClick={() => { setEditing(null); setShowForm(true); }}>Create draft</button>}</div>
    {error && <div role="alert" className="alert">{error} <button onClick={() => { setError(""); setRefresh(n => n + 1); }}>Refresh</button></div>}
    {notice && <p role="status" className="success">{notice}</p>}
    {!requirements && !error && <p role="status">Loading requirements…</p>}
    {project && <RequirementExtraction projectId={projectId} canWrite={canWrite} canCancel={canReview} externalAiConsent={project.external_ai_consent === true} onComplete={() => setRefresh(n => n + 1)} />}
    {showForm && <section className="panel"><h2>{editing ? `Revise ${editing.code}` : "New requirement draft"}</h2>
      <p>Edits create a new draft revision. Published baselines retain their original revisions.</p>
      <form key={editing?.id ?? "new"} onSubmit={save} className="stack">
        <label>Title<input name="title" required maxLength={200} defaultValue={current?.title} /></label>
        <label>Requirement<textarea name="content" required maxLength={10000} defaultValue={current?.content} /></label>
        <RequirementEvidencePicker projectId={projectId} initial={current} />
        <div><button className="primary" disabled={busy} type="submit">{busy ? "Saving…" : "Save draft"}</button> <button type="button" disabled={busy} onClick={() => setShowForm(false)}>Cancel</button></div>
      </form></section>}
    {transformAction && <section className="panel"><h2>{transformAction === "split" ? "Split requirement" : "Merge requirements"}</h2>
      <p>Parent revisions are retained for existing baselines and marked superseded for future baselines. Every new draft must cite an exact source passage.</p>
      <p>Parents: {transformParents.map(parent => parent.code).join(", ")}</p>
      <form className="stack" onSubmit={saveTransform}>
        {Array.from({ length: childCount }, (_, index) => {
          const parentVersion = transformParents[0]?.versions.find(version => version.version_number === transformParents[0].current_version);
          return <fieldset key={index} className="stack"><legend>Child draft {index + 1}</legend>
            <label>Title<input name={`child_${index}_title`} required maxLength={200} /></label>
            <label>Requirement<textarea name={`child_${index}_content`} required maxLength={10000} /></label>
            <RequirementEvidencePicker projectId={projectId} initial={parentVersion} namePrefix={`child_${index}_`} />
            {transformAction === "split" && childCount > 2 && <button type="button" onClick={() => setChildCount(count => count - 1)}>Remove this child</button>}
          </fieldset>;
        })}
        {transformAction === "split" && <button type="button" disabled={childCount >= 10} onClick={() => setChildCount(count => Math.min(count + 1, 10))}>Add another child requirement</button>}
        <div><button className="primary" disabled={busy}>{busy ? "Saving…" : transformAction === "split" ? "Create split drafts" : "Create merged draft"}</button>{" "}
          <button type="button" disabled={busy} onClick={() => { setTransformAction(null); setTransformParents([]); }}>Cancel</button></div>
      </form>
    </section>}
    {requirements?.items.length === 0 && <section className="panel"><p>No requirement drafts yet. Create a draft using evidence from your project documents.</p></section>}
    <div className="stack">{requirements?.items.map(requirement => <section className="panel" key={requirement.id}>
      <div className="section-heading"><h2>{requirement.code}</h2><span>{requirement.status}</span>{canWrite && requirement.status === "active" && <button disabled={busy} onClick={() => { setEditing(requirement); setShowForm(true); }}>Create revision</button>}</div>
      {canReview && requirement.status === "active" && <label><input type="checkbox" checked={Boolean(mergeSelected[requirement.id])} onChange={event => setMergeSelected(previous => {
        const next = { ...previous };
        if (event.target.checked) next[requirement.id] = requirement;
        else delete next[requirement.id];
        return next;
      })} /> Select for merge</label>}
      {requirement.versions.map(version => <details key={version.id} open={version.version_number === requirement.current_version}>
        <summary>v{version.version_number} · {version.title} · {version.status}</summary>
        <p>{version.content}</p>{version.source_quote ? <blockquote>{version.source_quote}</blockquote> : <p>Source evidence is required before approval.</p>}
        {canReview && requirement.status === "active" && version.status === "approved" && <label><input type="checkbox" checked={selected[requirement.id] === version.id} onChange={e => setSelected(previous => { const next = { ...previous }; if (e.target.checked) next[requirement.id] = version.id; else delete next[requirement.id]; return next; })} /> Include this revision in the next baseline</label>}
        {canReview && version.status === "draft" && version.version_number === requirement.current_version && <div>
          <button disabled={busy || !version.source_quote} onClick={() => void mutate(`${base}/requirements/${requirement.id}/approve`, { expected_version: version.version_number }, `${requirement.code} approved.`)}>Approve</button>{" "}
          <button disabled={busy} onClick={() => void mutate(`${base}/requirements/${requirement.id}/reject`, { expected_version: version.version_number }, `${requirement.code} rejected.`)}>Reject</button>
        </div>}
      </details>)}
      {canReview && requirement.status === "active" && <button disabled={busy} onClick={() => {
        setTransformAction("split");
        setTransformParents([requirement]);
        setChildCount(2);
      }}>Split into drafts</button>}
      {(requirement.lineage ?? []).length > 0 && <details><summary>Requirement lineage</summary>{(requirement.lineage ?? []).map(edge => <p key={edge.id}>{edge.action}: {edge.parent_requirement_code} → {edge.child_requirement_code}</p>)}</details>}
    </section>)}</div>
    {requirements && <nav aria-label="Requirement pages"><button disabled={page === 1 || busy} onClick={() => setPage(p => p - 1)}>Previous</button> Page {page} <button disabled={page * 25 >= requirements.total || busy} onClick={() => setPage(p => p + 1)}>Next</button></nav>}
    {canReview && <section className="panel"><h2>Publish selected scope</h2><p>{Object.keys(selected).length} approved revisions selected. Selections persist across pages; only one revision per requirement can be selected.</p>
      <button className="primary" disabled={busy || !Object.keys(selected).length} onClick={async () => { if (await mutate(`${base}/baselines`, { requirement_version_ids: Object.values(selected).sort() }, "Baseline published.", true)) setSelected({}); }}>Publish baseline</button>
    </section>}
    {canReview && Object.keys(mergeSelected).length >= 2 && <section className="panel"><h2>Merge selected requirements</h2>
      <p>{Object.values(mergeSelected).map(requirement => requirement.code).join(", ")} will become superseded; their historical baseline versions remain unchanged.</p>
      <button disabled={busy} onClick={() => {
        setTransformAction("merge");
        setTransformParents(Object.values(mergeSelected));
        setChildCount(1);
      }}>Create merged draft</button>{" "}
      <button disabled={busy} onClick={() => setMergeSelected({})}>Clear merge selection</button>
    </section>}
    <section className="panel"><h2>Published baselines</h2>{baselines.length ? baselines.map(b => <details key={b.id}><summary>B{b.number} · {b.items.length} requirements</summary><ul>{b.items.map(item => <li key={item.requirement_version_id}>{item.requirement_code} · revision {item.requirement_version_id}</li>)}</ul></details>) : <p>No published baselines on this page.</p>}
      <nav aria-label="Baseline pages"><button disabled={baselinePage === 1} onClick={() => setBaselinePage(p => p - 1)}>Previous</button> Page {baselinePage} <button disabled={baselines.length < 25} onClick={() => setBaselinePage(p => p + 1)}>Next</button></nav>
    </section>
  </>;
}
