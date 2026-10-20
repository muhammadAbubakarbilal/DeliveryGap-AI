"use client";

import Link from "next/link";
import { use, useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, Check, FileText, Settings2, ShieldCheck, Users } from "lucide-react";
import { useSession } from "@/components/shell";
import { api, message, type Member, type Project } from "@/lib/api";

export default function ProjectDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const session = useSession();
  const [project, setProject] = useState<Project | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("overview");
  const manage = session.user.is_admin || project?.role === "lead";
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api<Project>(`/projects/${id}`, { signal: controller.signal }), api<Member[]>(`/projects/${id}/members`, { signal: controller.signal })]).then(([p, m]) => { setProject(p); setMembers(m); }).catch(e => { if (!controller.signal.aborted) setError(message(e)); });
    return () => controller.abort();
  }, [id, reload]);
  async function mutate(path: string, method: string, body?: object) {
    setBusy(true); setError(""); setNotice("");
    try { await api(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }, session.csrf_token); setNotice("Changes saved."); setReload(x => x + 1); return true; }
    catch (e) { setError(message(e)); return false; } finally { setBusy(false); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    await mutate(`/projects/${id}`, "PATCH", { name: form.get("name"), description: form.get("description"), status: form.get("status"), revision: project?.revision });
  }
  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const element = event.currentTarget; const form = new FormData(element);
    if (await mutate(`/projects/${id}/members`, "POST", { email: form.get("email"), role: form.get("role") })) element.reset();
  }
  return <><Link className="back-link" href="/projects"><ArrowLeft size={15} /> All projects</Link>{error && <div role="alert" className="alert">{error} <button className="text-button" onClick={() => { setError(""); setReload(x => x + 1); }}>Refresh</button></div>}{notice && <div role="status" className="success"><Check size={16} />{notice}</div>}
    {!project ? !error && <div className="loading" role="status">Loading project…</div> : <><div className="page-heading"><div><div className="eyebrow">PROJECT WORKSPACE</div><h1>{project.name}</h1><p>{project.description || "Give your team a shared starting point."}</p></div><span className={`badge ${project.status === "active" ? "green" : ""}`}>{project.status}</span></div>
      <Link className="back-link" href={`/projects/${id}/documents`}><FileText size={16} /> Documents and sources</Link>
      <Link className="back-link" href={`/projects/${id}/requirements`}><Check size={16} /> Review requirements and baselines</Link>
      <Link className="back-link" href={`/projects/${id}/evidence`}><FileText size={16} /> Delivery evidence and traceability</Link>
      <Link className="back-link" href={`/projects/${id}/analysis`}><FileText size={16} /> Change findings</Link>
      <nav className="tabs" aria-label="Project sections">{[{ id: "overview", label: "Overview", icon: FileText }, { id: "members", label: "Members", icon: Users }, ...(manage ? [{ id: "settings", label: "Settings", icon: Settings2 }] : [])].map(item => <button key={item.id} aria-current={tab === item.id ? "page" : undefined} className={tab === item.id ? "selected" : ""} onClick={() => setTab(item.id)}><item.icon size={16} />{item.label}</button>)}</nav>
      {tab === "overview" && <div className="detail-grid"><section className="panel"><div className="section-heading"><h2>Project setup</h2><span className="badge green">Ready</span></div><div className="check-row"><span className="step-icon"><Check size={16} /></span><div><strong>Workspace created</strong><p>Your project and access settings are saved.</p></div></div><div className="check-row"><span className="step-icon"><Users size={16} /></span><div><strong>{project.member_count} {project.member_count === 1 ? "person has" : "people have"} access</strong><p>Assign leads, members, and read-only reviewers.</p></div><button className="text-button" onClick={() => setTab("members")}>View members</button></div><div className="next-step"><FileText size={22} /><div><strong>Next milestone: approved scope</strong><p>Upload sources, review grounded requirements, and publish a baseline.</p></div></div></section><section className="panel"><h2>Access at a glance</h2><dl><dt>Your role</dt><dd className="role-label">{project.role}</dd><dt>Created</dt><dd>{new Date(project.created_at).toLocaleDateString()}</dd><dt>Visibility</dt><dd><ShieldCheck size={14} /> Project members</dd></dl><p className="subtle">Workspace administrators have audited access to all projects.</p></section></div>}
      {tab === "members" && <section className="panel"><div className="section-heading"><h2>People with access</h2><span className="count">{members.length}</span></div><p className="subtle">Leads manage scope and access. Members contribute. Reviewers can view only.</p><div className="table-scroll"><table><thead><tr><th>Person</th><th>Role</th>{manage && <th><span className="sr-only">Actions</span></th>}</tr></thead><tbody>{members.map(member => <tr key={member.user_id}><td><strong>{member.display_name}</strong><small>{member.email}{!member.is_active && " · Inactive"}</small></td><td>{manage ? <select aria-label={`Role for ${member.display_name}`} value={member.role} disabled={busy} onChange={e => mutate(`/projects/${id}/members/${member.user_id}`, "PATCH", { role: e.target.value })}><option value="lead">Lead</option><option value="member">Member</option><option value="reviewer">Reviewer</option></select> : <span className="badge">{member.role}</span>}</td>{manage && <td><button className="text-button danger" disabled={busy} onClick={() => { if (window.confirm(`Remove ${member.display_name} from this project?`)) void mutate(`/projects/${id}/members/${member.user_id}`, "DELETE"); }}>Remove</button></td>}</tr>)}</tbody></table></div>{manage && <form className="member-form" onSubmit={add}><label>Workspace user’s email<input name="email" type="email" required placeholder="teammate@company.com" /></label><label>Role<select name="role" defaultValue="member"><option value="member">Member</option><option value="reviewer">Reviewer</option><option value="lead">Lead</option></select></label><button className="primary" disabled={busy}>Add member</button><p className="subtle">The user must already have a workspace account.</p></form>}</section>}
      {tab === "settings" && manage && <>
        <section className="panel"><h2>Project settings</h2><form key={project.revision} onSubmit={save} className="settings-form"><label>Project name<input name="name" required maxLength={120} defaultValue={project.name} /></label><label>Description<textarea name="description" maxLength={4000} defaultValue={project.description} rows={4} /></label><label>Status<select name="status" defaultValue={project.status}><option value="active">Active</option><option value="archived">Archived</option></select></label><p className="subtle">Archiving keeps the project and its access history. It does not delete data.</p><button className="primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button></form></section>
        <section className="panel"><h2>External AI processing</h2>
          <p>When enabled, source passages, change requests, and approved requirements may be sent to the configured Neon AI Gateway for extraction, embeddings, and analysis. Never use actual client documents without written authorization.</p>
          <p role="status">External AI processing is {project.external_ai_consent ? "enabled" : "disabled"} for this project.</p>
          <p className="subtle">Revoking consent blocks new jobs and prevents workers from saving results after a permission recheck. A provider request already in flight may have been transmitted.</p>
          <button className={project.external_ai_consent ? "" : "primary"} disabled={busy || (project.status !== "active" && !project.external_ai_consent)} onClick={() => void mutate(`/projects/${id}/ai-consent`, "PATCH", { enabled: !project.external_ai_consent })}>
            {project.external_ai_consent ? "Revoke external AI consent" : "Enable external AI processing"}
          </button>
        </section>
      </>}
    </>}</>;
}
