import React, { useState } from "react";
import { LogIn, ShieldPlus } from "lucide-react";
import { api } from "../api";

const demoAccounts = [
  ["Pharmacy owner", "owner@aster.demo", "AsterDemo!2026"],
  ["Inventory manager", "manager@lakeside.demo", "LakesideDemo!2026"],
  ["Read-only user", "viewer@aster.demo", "ViewerDemo!2026"],
];

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("owner@aster.demo");
  const [password, setPassword] = useState("AsterDemo!2026");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    try { const result = await api.login({ email, password }); api.setSession(result.token); onLogin(result.user); }
    catch (err) { setError(err.message || "Unable to sign in."); }
    finally { setBusy(false); }
  }
  return <main className="login-shell"><section className="login-card">
    <div className="login-brand"><span><ShieldPlus size={25}/></span><div><strong>MedGuard AI</strong><small>PHARMACY SUPPLY RESILIENCE</small></div></div>
    <div className="login-intro"><span>LOCAL DEMO ACCESS</span><h1>Sign in to the pharmacy workspace</h1><p>Use a seeded demo account to explore the full local workflow. No live pharmacy records or external services are connected.</p></div>
    <form onSubmit={submit} className="login-form"><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required /></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required /></label>{error && <div className="login-error">{error}</div>}<button className="button button-primary" disabled={busy}>{busy ? "Signing in…" : <><LogIn size={16}/>Sign in</>}</button></form>
    <div className="demo-account-list"><strong>Demo accounts</strong>{demoAccounts.map(([role, address, secret])=><button key={address} type="button" onClick={()=>{setEmail(address);setPassword(secret)}}><span>{role}</span><small>{address}</small></button>)}</div>
    <p className="login-note">These local accounts demonstrate role-aware access. They are not production identity accounts.</p>
  </section></main>;
}
