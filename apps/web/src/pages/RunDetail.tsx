import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, RunDetail as Detail } from "../api/client";

export default function RunDetail() {
  const { id } = useParams();
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.run(id).then(setData).catch((e) => setError(String(e.message || e)));
  }, [id]);

  if (error) return <div className="warn-banner">{error}</div>;
  if (!data) return <p className="muted">Loading run…</p>;
  const { run, events, candidates } = data;
  const d = run.diagnosis;

  return (
    <div>
      <h2>Run {run.github_run_id}</h2>
      <div className="row">
        <span className="badge">{run.state}</span>
        {run.simulated && <span className="badge sim">simulated agent</span>}
        <button className="btn secondary" onClick={() => api.cancel(run.id)}>Cancel</button>
      </div>
      <p className="muted">
        source <code>{run.source_sha}</code> · execution <code>{run.execution_sha}</code> · base <code>{run.base_sha}</code>
      </p>
      {d && (
        <div className="card">
          <h3>Diagnosis</h3>
          <p><strong>{d.failure_category}</strong> — {d.hypothesis}</p>
          <p className="muted">{d.expected_behavior}</p>
        </div>
      )}
      {run.limitations && run.limitations.length > 0 && (
        <div className="warn-banner">
          {run.limitations.map((l) => <div key={l}>{l}</div>)}
        </div>
      )}
      <h3>Timeline</h3>
      <ul className="timeline">
        {events.map((e, i) => (
          <li key={i}><span className="mono">{e.state}</span> · {e.actor} · {e.reason} {e.detail && <span className="muted">{e.detail}</span>}</li>
        ))}
      </ul>
      <h3>Candidates</h3>
      {candidates.length === 0 && <p className="muted">No patch proposed yet.</p>}
      {candidates.map((c) => (
        <div className="card" key={c.id}>
          <div className="row">
            <span className={`badge ${c.verified ? "ok" : "danger"}`}>{c.verified ? `verified (${c.badge})` : "not verified"}</span>
            <span className="mono">{c.patch_digest.slice(0, 12)}</span>
            <Link to={`/runs/${run.id}/patch/${c.id}`}>Review patch</Link>
          </div>
          <p className="muted">{(c.changed_files || []).join(", ") || "no files"} · {c.model}</p>
        </div>
      ))}
    </div>
  );
}
