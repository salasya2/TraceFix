import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function Login() {
  const [email, setEmail] = useState("maintainer@tracefix.local");
  const [error, setError] = useState<string | null>(null);
  const [devLogin, setDevLogin] = useState(true);
  const [oidc, setOidc] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    api.authConfig()
      .then((c) => {
        setDevLogin(c.dev_login);
        setOidc(c.oidc_configured);
      })
      .catch(() => undefined);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const res = await fetch("/v1/auth/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) {
      setError("Login failed");
      return;
    }
    nav("/");
  }

  async function startOidc() {
    const res = await fetch("/v1/auth/oidc/start", { credentials: "include" });
    if (!res.ok) {
      setError("OIDC is not configured");
      return;
    }
    const body = await res.json();
    window.location.href = body.authorization_url;
  }

  return (
    <div className="card" style={{ maxWidth: 420 }}>
      <h2>Sign in</h2>
      {devLogin ? (
        <>
          <p className="muted">Development login. Production uses OIDC authorization-code + PKCE.</p>
          <form onSubmit={onSubmit}>
            <input value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%", margin: "12px 0", padding: 8 }} />
            <button className="btn" type="submit">Continue</button>
          </form>
        </>
      ) : (
        <p className="muted">Development login is disabled. Use your organization identity provider.</p>
      )}
      {oidc && (
        <p>
          <button className="btn" type="button" onClick={startOidc}>Sign in with SSO</button>
        </p>
      )}
      {error && <p className="warn-banner">{error}</p>}
    </div>
  );
}
