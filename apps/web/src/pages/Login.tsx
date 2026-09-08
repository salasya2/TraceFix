import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const [email, setEmail] = useState("maintainer@tracefix.local");
  const [error, setError] = useState<string | null>(null);
  const nav = useNavigate();

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

  return (
    <div className="card" style={{ maxWidth: 420 }}>
      <h2>Sign in</h2>
      <p className="muted">Dev auth. OIDC authorization-code + PKCE is used when TRACEFIX_AUTH_MODE=oidc.</p>
      <form onSubmit={onSubmit}>
        <input value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%", margin: "12px 0", padding: 8 }} />
        <button className="btn" type="submit">Continue</button>
      </form>
      {error && <p className="warn-banner">{error}</p>}
    </div>
  );
}
