import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, CandidateDetail, PublishResult } from "../api/client";

export default function PatchReview() {
  const { candidateId } = useParams();
  const [data, setData] = useState<CandidateDetail | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [pub, setPub] = useState<PublishResult | null>(null);

  useEffect(() => {
    if (!candidateId) return;
    api.candidate(candidateId).then(setData).catch((e) => setMsg(String(e.message || e)));
  }, [candidateId]);

  if (!data) return <p className="muted">{msg || "Loading patch…"}</p>;

  const lines = (data.patch || "").split("\n");

  async function approve() {
    if (!data) return;
    try {
      await api.approve(data.id, data.patch_digest);
      setMsg("Approved. Approval expires in 30 minutes and is bound to this digest.");
    } catch (e) {
      setMsg(String((e as Error).message));
    }
  }
  async function publish() {
    if (!data) return;
    try {
      const result = await api.publish(data.id);
      setPub(result);
      setMsg(`Publication mode: ${result.mode}`);
    } catch (e) {
      setMsg(String((e as Error).message));
    }
  }

  return (
    <div>
      <h2>Patch review</h2>
      <div className="row">
        <span className={`badge ${data.verified ? "ok" : "danger"}`}>{data.verified ? `verified ${data.badge}` : "unverified"}</span>
        <span className="mono">{data.patch_digest}</span>
      </div>
      {data.badge !== "full" && (
        <div className="warn-banner">
          Full-verification badge withheld or incomplete. Do not treat this as a green suite.
        </div>
      )}
      <pre className="diff">
        {lines.map((line, i) => (
          <div key={i} className={line.startsWith("+") ? "add" : line.startsWith("-") ? "del" : ""}>
            {line}
          </div>
        ))}
      </pre>
      <h3>Limitations</h3>
      <ul>{(data.limitations || []).map((l) => <li key={l}>{l}</li>)}</ul>
      <div className="row">
        <button className="btn" onClick={approve} disabled={!data.verified}>Approve digest</button>
        <button className="btn secondary" onClick={publish}>Publish / download</button>
      </div>
      {msg && <p>{msg}</p>}
      {pub?.pr_url && <p>Draft PR: <a href={pub.pr_url}>{pub.pr_url}</a></p>}
      {pub?.mode === "patch_download" && <p>Patch-download mode — repository workflows were not admitted for live publication.</p>}
    </div>
  );
}
