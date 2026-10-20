"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ArrowRight, Check, ShieldCheck, Waypoints } from "lucide-react";
import { api, message } from "@/lib/api";

export default function Login() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [managed, setManaged] = useState(false);
  const [provider, setProvider] = useState("local");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api<{ neon: boolean }>("/auth/options", { signal: controller.signal })
      .then(options => { setManaged(options.neon); if (options.neon) setProvider("neon"); setReady(true); })
      .catch(error => { if (!controller.signal.aborted) setError(message(error)); });
    return () => controller.abort();
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const data = new FormData(event.currentTarget);
    try {
      if (provider === "neon") {
        const { neonAuth } = await import("@/lib/neon-auth");
        const signedIn = await neonAuth.signIn.email({ email: String(data.get("email")), password: String(data.get("password")) });
        if (signedIn.error) throw new Error(signedIn.error.message ?? "Neon sign-in failed.");
        const result = await neonAuth.token();
        if (result.error || !result.data?.token) throw new Error("Neon could not verify your session.");
        await api("/auth/neon", { method: "POST", headers: { Authorization: `Bearer ${result.data.token}` } });
      } else {
        await api("/auth/login", { method: "POST", body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) });
      }
      // Read the new session cookie on a fresh request, without cached signed-out route data.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/projects");
    }
    catch (e) { setError(message(e)); setBusy(false); }
  }
  return <div className="login-layout"><section className="login-story"><div className="brand"><span className="brand-mark"><Waypoints /></span>DeliveryGap<span className="brand-ai">AI</span></div><div><div className="eyebrow">CLARITY FROM SCOPE TO DELIVERY</div><h1>Keep the agreement<br />in the picture.</h1><p>Bring requirements, conversations, and delivery evidence together. Make every review decision traceable.</p><div className="story-steps">{["Start with approved scope", "Review changes with evidence", "Keep people in control"].map(x => <span key={x}><Check size={16} />{x}</span>)}</div></div><small>Built for thoughtful engineering teams.</small></section>
    <main id="main-content" className="login-main"><div className="login-card"><span className="private-badge"><ShieldCheck size={14} /> Internal workspace</span><h2>Welcome back.</h2><p>Sign in to your DeliveryGap workspace.</p><form onSubmit={submit}>{managed && <label>Sign-in method<select aria-label="Sign-in method" value={provider} onChange={event => setProvider(event.target.value)}><option value="neon">Neon account</option><option value="local">Local workspace account</option></select></label>}<label>Email address<input name="email" type="email" autoComplete="username" required placeholder="you@company.com" /></label><label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={256} placeholder="Enter your password" /></label>{error && <div role="alert" className="alert">{error}</div>}<button className="primary full" disabled={busy || !ready}>{!ready ? "Connecting…" : busy ? "Signing in…" : "Sign in"}<ArrowRight size={17} /></button></form><div className="login-help">Access is managed by your workspace administrator.<br />Contact them if you need an account.</div></div></main></div>;
}
