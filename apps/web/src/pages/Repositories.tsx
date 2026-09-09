import { FormEvent, useEffect, useState } from "react";
import { api, PolicyDoc, Repo } from "../api/client";

export default function Repositories() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [version, setVersion] = useState<number>(0);
  const [paths, setPaths] = useState("src/");
  const [mode, setMode] = useState("approval_required");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    api.repos().then((r) => setRepos(r.items)).catch(() => setRepos([]));
  }, []);

  async function loadPolicy(id: string) {
    setSelected(id);
    const policy = await api.repoPolicy(id);
    setVersion(policy.version);
    setMode(policy.document.mode);
    setPaths((policy.document.source_paths || []).join("\n"));
    setStatus(null);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    const document: PolicyDoc = {
      schema_version: 1,
      mode,
      source_paths: paths.split(/\n+/).map((s) => s.trim()).filter(Boolean),
      eligible_events: ["push", "pull_request"],
      execution_profile: "python312-pytest-v1",
    };
    try {
      const updated = await api.updatePolicy(selected, document, version);
      setVersion(updated.version);
      setStatus(`Saved policy version ${updated.version}`);
    } catch (err) {
      setStatus(String(err));
    }
  }

  if (repos.length === 0) return <div className="empty">No repositories onboarded.</div>;
  return (
    <div>
      <h2>Repository settings</h2>
      <table className="table">
        <thead>
          <tr><th>Name</th><th>Mode</th><th>Publication</th><th>Selected</th><th></th></tr>
        </thead>
        <tbody>
          {repos.map((r) => (
            <tr key={r.id}>
              <td>{r.full_name}</td>
              <td>{r.mode}</td>
              <td>{r.publication_mode}</td>
              <td>{r.selected ? "yes" : "no"}</td>
              <td><button className="btn" type="button" onClick={() => loadPolicy(r.id)}>Edit policy</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {selected && (
        <form className="card" onSubmit={save} style={{ marginTop: 16 }}>
          <h3>Policy version {version}</h3>
          <label>
            Mode
            <select value={mode} onChange={(e) => setMode(e.target.value)} style={{ display: "block", margin: "8px 0" }}>
              <option value="approval_required">approval_required</option>
              <option value="report_only">report_only</option>
              <option value="disabled">disabled</option>
            </select>
          </label>
          <label>
            Source paths (one per line)
            <textarea value={paths} onChange={(e) => setPaths(e.target.value)} rows={4} style={{ width: "100%", margin: "8px 0" }} />
          </label>
          <button className="btn" type="submit">Save policy</button>
          {status && <p>{status}</p>}
        </form>
      )}
    </div>
  );
}
