export default function SettingsPage() {
  return (
    <div>
      <h2>Organization</h2>
      <div className="card">
        <h3>Identity</h3>
        <p>Dev auth maps maintainer@tracefix.local to the Acme owner. OIDC is used when TRACEFIX_AUTH_MODE=oidc.</p>
      </div>
      <div className="card">
        <h3>Emergency stop</h3>
        <p className="muted">Stops new sandboxes for the tenant. Existing leases are swept independently of workflow health.</p>
      </div>
      <div className="card">
        <h3>Retention</h3>
        <p>Raw artifacts 7 days · redacted reports 30 days · audit metadata 90 days (configurable).</p>
      </div>
    </div>
  );
}
