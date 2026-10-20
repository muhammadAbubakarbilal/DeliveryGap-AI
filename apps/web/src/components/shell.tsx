"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useState } from "react";
import { ArrowUpRight, Boxes, ChevronRight, LayoutGrid, LogOut, ShieldCheck, Waypoints } from "lucide-react";
import { api, message, type Session } from "@/lib/api";

const SessionContext = createContext<Session | null>(null);
export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("Session provider is missing");
  return context;
}

export function Shell({ session, children }: { session: Session; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [error, setError] = useState("");
  const [leaving, setLeaving] = useState(false);
  async function logout() {
    setLeaving(true);
    try {
      await api("/auth/logout", { method: "POST" }, session.csrf_token);
      if (session.auth_provider === "neon") {
        const { neonAuth } = await import("@/lib/neon-auth");
        const result = await neonAuth.signOut();
        if (result.error) throw new Error("Workspace signed out, but Neon sign-out failed.");
      }
      router.replace("/login"); router.refresh();
    }
    catch (e) { setError(message(e)); setLeaving(false); }
  }
  return <SessionContext value={session}><div className="app-layout">
    <aside className="sidebar">
      <Link className="brand" href="/projects"><span className="brand-mark"><Waypoints size={23} /></span><span>DeliveryGap<span className="brand-ai">AI</span></span></Link>
      <div className="workspace-label"><span className="workspace-icon">D</span><div>Engineering workspace<small>Internal workspace</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">
        <Link className={`nav-item ${pathname.startsWith("/projects") ? "active" : ""}`} href="/projects"><LayoutGrid size={18} /> Projects <ChevronRight size={14} className="nav-arrow" /></Link>
        {session.user.is_admin && <Link className={`nav-item ${pathname.startsWith("/admin") ? "active" : ""}`} href="/admin/users"><ShieldCheck size={18} /> People & access</Link>}
      </nav>
      <div className="sidebar-note"><Boxes size={21} /><strong>Evidence before assumptions.</strong><p>A shared place for approved scope, review decisions, and delivery evidence.</p><span>Foundation release <ArrowUpRight size={13} /></span></div>
      <div className="user-block"><span className="avatar">{session.user.display_name.slice(0, 2).toUpperCase()}</span><div><strong>{session.user.display_name}</strong><small>{session.user.is_admin ? "Workspace admin" : "Workspace member"}</small></div><button className="icon-button" onClick={logout} disabled={leaving} aria-label="Sign out"><LogOut size={17} /></button></div>
    </aside>
    <div className="main-column"><header className="topbar"><span>Workspace <ChevronRight size={14} /> {pathname.startsWith("/admin") ? "People & access" : "Projects"}</span><span className="private-badge"><ShieldCheck size={13} /> Private workspace</span></header>
      <main id="main-content">{error && <div role="alert" className="alert">{error}</div>}{children}</main>
      <footer>DeliveryGap AI <span>Human decisions. Traceable evidence.</span></footer>
    </div>
  </div></SessionContext>;
}
