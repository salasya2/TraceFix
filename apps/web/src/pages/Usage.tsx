import { useEffect, useState } from "react";
import { api, Audit } from "../api/client";

export default function UsagePage() {
  const [usage, setUsage] = useState<{ reserved_usd: number; settled_usd: number } | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);
  useEffect(() => {
    api.usage().then(setUsage);
    api.audit().then((a) => setAudit(a.items));
  }, []);
  return (
    <div>
      <h2>Usage and audit</h2>
      <div className="grid">
        <div className="card"><h3>Reserved USD</h3><div className="n">{usage?.reserved_usd ?? 0}</div></div>
        <div className="card"><h3>Settled USD</h3><div className="n">{usage?.settled_usd ?? 0}</div></div>
      </div>
      <h3>Audit</h3>
      <table className="table">
        <thead><tr><th>Action</th><th>Actor</th><th>Target</th></tr></thead>
        <tbody>
          {audit.map((a) => (
            <tr key={a.id}><td>{a.action}</td><td>{a.actor}</td><td>{a.target_type}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
