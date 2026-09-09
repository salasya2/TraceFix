import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function SettingsPage() {
  const [me, setMe] = useState<{ email: string; role: string; tenant_id: string } | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  async function stop(engaged: boolean) {
    try {
      await api.emergencyStop(engaged);
      setMessage(engaged ? "Tenant emergency stop engaged." : "Tenant emergency stop cleared.");
    } catch (err) {
      setMessage(String(err));
    }
  }

  return (
    <div>
      <h2>Organization</h2>
      <div className="card">
        <h3>Identity</h3>
        {me ? (
          <p>
            {me.email} · {me.role} · tenant {me.tenant_id}
          </p>
        ) : (
          <p className="muted">Sign in to view membership.</p>
        )}
      </div>
      <div className="card">
        <h3>Emergency stop</h3>
        <p className="muted">Stops new sandboxes for this tenant only. Other tenants are unaffected.</p>
        <p>
          <button className="btn" type="button" onClick={() => stop(true)}>Engage stop</button>{" "}
          <button className="btn" type="button" onClick={() => stop(false)}>Clear stop</button>
        </p>
        {message && <p>{message}</p>}
      </div>
      <div className="card">
        <h3>Retention</h3>
        <p>Raw artifacts 7 days · redacted reports 30 days · audit metadata 90 days (configurable).</p>
      </div>
    </div>
  );
}
