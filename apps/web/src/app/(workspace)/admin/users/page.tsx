"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Plus, ShieldCheck, X } from "lucide-react";
import { useSession } from "@/components/shell";
import { api, message, type User } from "@/lib/api";

export default function People() {
  const session = useSession();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!session.user.is_admin) return;
    const controller = new AbortController();
    api<User[]>(`/admin/users?page=${page}`, { signal: controller.signal }).then(setUsers).catch(e => { if (!controller.signal.aborted) setError(message(e)); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [page, reload, session.user.is_admin]);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); const form = new FormData(event.currentTarget);
    try { await api("/admin/users", { method: "POST", body: JSON.stringify({ email: form.get("email"), display_name: form.get("display_name"), password: form.get("password") }) }, session.csrf_token); setShowForm(false); setPage(1); setReload(x => x + 1); }
    catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function toggle(user: User) {
    if (!window.confirm(`${user.is_active ? "Disable" : "Enable"} ${user.display_name}’s account?`)) return;
    setBusy(true); setError("");
    try { await api(`/admin/users/${user.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !user.is_active }) }, session.csrf_token); setReload(x => x + 1); }
    catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  if (!session.user.is_admin) return <div role="alert" className="alert">Workspace administrator access is required.</div>;
  return <><div className="page-heading"><div><div className="eyebrow">WORKSPACE ADMINISTRATION</div><h1>People & access</h1><p>Create accounts, then assign project access where it’s needed.</p></div><button className="primary" onClick={() => setShowForm(true)}><Plus size={17} /> Add person</button></div>
    {error && <div role="alert" className="alert">{error}</div>}
    {showForm && <section className="panel create-panel"><div className="section-heading"><h2>Create workspace account</h2><button aria-label="Close account form" className="icon-button" onClick={() => setShowForm(false)}><X size={18} /></button></div><form onSubmit={create}><div className="form-grid"><label>Full name<input name="display_name" required maxLength={100} autoComplete="off" /></label><label>Email<input name="email" type="email" required autoComplete="off" /></label><label>Initial password<input name="password" type="password" minLength={12} maxLength={256} required autoComplete="new-password" /><small>At least 12 characters. Share privately with the account holder.</small></label></div><button className="primary" disabled={busy}>{busy ? "Creating…" : "Create account"}</button></form></section>}
    <section className="panel"><div className="section-heading"><h2>Workspace directory</h2><ShieldCheck size={20} /></div>{loading ? <div role="status" className="loading">Loading people…</div> : <div className="table-scroll"><table><thead><tr><th>Person</th><th>Workspace role</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{users.map(user => <tr key={user.id}><td><strong>{user.display_name}</strong><small>{user.email}</small></td><td>{user.is_admin ? "Administrator" : "Member"}</td><td><span className={`badge ${user.is_active ? "green" : ""}`}>{user.is_active ? "Active" : "Disabled"}</span></td><td>{!user.is_admin && <button disabled={busy} className="text-button" onClick={() => toggle(user)}>{user.is_active ? "Disable" : "Enable"}</button>}</td></tr>)}</tbody></table></div>}<div className="pagination"><button disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page}</span><button disabled={users.length < 25} onClick={() => setPage(p => p + 1)}>Next</button></div></section>
  </>;
}
