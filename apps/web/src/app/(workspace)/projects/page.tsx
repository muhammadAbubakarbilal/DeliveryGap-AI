"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, FolderKanban, Plus, Search, Users, X } from "lucide-react";
import { api, message, type ProjectPage } from "@/lib/api";
import { useSession } from "@/components/shell";

export default function Projects() {
  const session = useSession();
  const [data, setData] = useState<ProjectPage | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const creationKeys = useRef(new Map<string, string>());
  const creating = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => { api<ProjectPage>(`/projects?page=${page}&q=${encodeURIComponent(query)}`, { signal: controller.signal }).then(setData).catch(e => { if (!controller.signal.aborted) setError(message(e)); }); }, 180);
    return () => { clearTimeout(timeout); controller.abort(); };
  }, [page, query, reload]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (creating.current) return;
    creating.current = true;
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const body = JSON.stringify({ name: String(form.get("name") ?? "").trim(), description: String(form.get("description") ?? "").trim() });
    try {
      const key = creationKeys.current.get(body) ?? crypto.randomUUID();
      creationKeys.current.set(body, key);
      await api("/projects", { method: "POST", body, headers: { "Idempotency-Key": key } }, session.csrf_token);
      creationKeys.current.clear();
      setShowForm(false); setQuery(""); setPage(1); setReload(x => x + 1);
    }
    catch (e) { setError(`${message(e)} Submit the form again to retry.`); }
    finally { creating.current = false; setBusy(false); }
  }
  return <><div className="page-heading"><div><div className="eyebrow">YOUR WORKSPACE</div><h1>Projects</h1><p>Keep scope, decisions, and delivery evidence in one place.</p></div>{session.user.is_admin && <button className="primary" onClick={() => setShowForm(true)}><Plus size={17} /> New project</button>}</div>
    <section className="intro-banner"><div className="banner-icon"><FolderKanban size={26} /></div><div><h2>Good delivery starts with shared understanding.</h2><p>Create a project and bring your team together. Approved scope and evidence review come next.</p></div><span className="phase-tag">01 / FOUNDATION</span></section>
    {showForm && <section className="panel create-panel"><div className="section-heading"><h2>Create a project</h2><button className="icon-button" aria-label="Close create project form" onClick={() => setShowForm(false)}><X size={18} /></button></div><form onSubmit={create}><div className="form-grid"><label>Project name<input name="name" autoFocus required maxLength={120} placeholder="e.g. ShopFlow Checkout" /></label><label>Description<textarea name="description" maxLength={4000} placeholder="What is this project building?" /></label></div><button className="primary" disabled={busy}>{busy ? "Creating…" : "Create project"}<ArrowRight size={16} /></button></form></section>}
    {error && <div role="alert" className="alert">{error} <button className="text-button" onClick={() => { setError(""); setReload(x => x + 1); }}>Retry</button></div>}
    <div className="list-toolbar"><h2>All projects <span className="count">{data?.total ?? "—"}</span></h2><label className="search"><Search size={17} /><input aria-label="Search projects" placeholder="Search projects…" value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} /></label></div>
    {!data && !error ? <div role="status" className="loading">Loading projects…</div> : data?.items.length ? <div className="project-grid">{data.items.map(project => <Link className="project-card" key={project.id} href={`/projects/${project.id}`}><div className="card-top"><span className="project-icon"><FolderKanban size={22} /></span><span className={`badge ${project.status === "active" ? "green" : ""}`}>{project.status}</span></div><h3>{project.name}</h3><p>{project.description || "No description added yet."}</p><div className="card-meta"><span><Users size={14} /> {project.member_count} {project.member_count === 1 ? "member" : "members"}</span><span className="role-label">{project.role}</span></div><div className="card-bottom"><span>Created {new Date(project.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</span><ArrowRight size={16} /></div></Link>)}</div> : data && <div className="empty-state"><FolderKanban size={36} /><h2>{query ? "No matching projects" : "Your first project starts here"}</h2><p>{query ? "Try a different project name." : session.user.is_admin ? "Create a project to define its purpose and invite your team." : "Your administrator will add you to a project. It will appear here once you have access."}</p>{!query && session.user.is_admin && <button className="primary" onClick={() => setShowForm(true)}><Plus size={16} /> Create project</button>}</div>}
    {data && data.total > data.page_size && <div className="pagination"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page} of {Math.ceil(data.total / data.page_size)}</span><button disabled={page * data.page_size >= data.total} onClick={() => setPage(p => p + 1)}>Next</button></div>}
  </>;
}
