import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Run } from "../api/client";

export default function Overview() {
  const [stats, setStats] = useState<{ active_runs: number; verified_candidates: number; unsuccessful: number; runs: number } | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.overview(), api.runs()])
      .then(([s, r]) => {
        setStats(s);
        setRuns(r.items);
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  if (error) return <div className="warn-banner">Provider or API failure: {error}</div>;
  if (!stats) return <p className="muted">Loading overview…</p>;
  if (stats.runs === 0) return <div className="empty">No investigations yet. Run <code>python scripts/tf.py demo</code>.</div>;

  return (
    <div>
      <h2>Overview</h2>
      <p className="muted">Spend and queue age are computed for the current tenant session.</p>
      <div className="grid">
        <div className="card"><h3>Active runs</h3><div className="n">{stats.active_runs}</div></div>
        <div className="card"><h3>Verified candidates</h3><div className="n">{stats.verified_candidates}</div></div>
        <div className="card"><h3>Unsuccessful</h3><div className="n">{stats.unsuccessful}</div></div>
        <div className="card"><h3>Total runs</h3><div className="n">{stats.runs}</div></div>
      </div>
      <h3>Recent runs</h3>
      <table className="table">
        <thead>
          <tr><th>State</th><th>GitHub run</th><th>SHA</th><th>Flags</th></tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td><Link to={`/runs/${run.id}`}>{run.state}</Link></td>
              <td className="mono">{run.github_run_id}</td>
              <td className="mono">{run.source_sha.slice(0, 12)}</td>
              <td>
                {run.simulated && <span className="badge sim">simulated agent</span>}{" "}
                <span className="badge">{run.reason_code || "—"}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
