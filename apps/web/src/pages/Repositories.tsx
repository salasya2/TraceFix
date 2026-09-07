import { useEffect, useState } from "react";
import { api, Repo } from "../api/client";

export default function Repositories() {
  const [repos, setRepos] = useState<Repo[]>([]);
  useEffect(() => {
    api.repos().then((r) => setRepos(r.items)).catch(() => setRepos([]));
  }, []);
  if (repos.length === 0) return <div className="empty">No repositories onboarded.</div>;
  return (
    <div>
      <h2>Repository settings</h2>
      <table className="table">
        <thead>
          <tr><th>Name</th><th>Mode</th><th>Publication</th><th>Selected</th></tr>
        </thead>
        <tbody>
          {repos.map((r) => (
            <tr key={r.id}>
              <td>{r.full_name}</td>
              <td>{r.mode}</td>
              <td>{r.publication_mode}</td>
              <td>{r.selected ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">Policy edits require an admin and optimistic concurrency on the policy version.</p>
    </div>
  );
}
