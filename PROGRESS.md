# TraceFix implementation progress

Updated: 2026-09-08

Checkout: `C:\Users\saite\OneDrive\Documents\Masters\FAANG\tracefix`

This file records **executable evidence**, not intent. Live GitHub App publication, paid model calls, gVisor RuntimeClass, and PostgreSQL RLS-as-a-non-owner remain environment-blocked.

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| 0 Contracts and threat model | implemented | `docs/adr/*`, `docs/threat-model.md`, policy schema |
| 1 Reproducible verifier | implemented + regression-tested | Exit code, timeout, and missing JUnit now fail closed (`tests/unit/test_verification_exit.py`). Execution goes through the broker. |
| 2 Durable ingestion | implemented locally | Outbox claims events, marks `dispatched_at` only after the investigation, and retries after injected crashes (`tests/chaos/test_outbox_crash.py`). Temporal worker binds runtime before polling. |
| 3 Constrained agent | fixture-complete; live provider selectable | `TRACEFIX_MODEL_PROVIDER` selects fixture / Anthropic / SpaceXAI. Bounded retry loop up to policy candidate limit. Pytest option flags rejected. |
| 4 Maintainer product | implemented for SSO + dev | Production rejects fixture emails (`tests/integration/test_auth_production.py`). OIDC callback exchanges code, verifies JWT, maps membership. Dev login is development-only. |
| 5 Hostile execution | fail-closed + broker boundary | Process/Docker/gVisor adapters. Docker no longer falls back to the host interpreter. gVisor schedules with `--runtime=runsc` when `runsc` exists; otherwise refuses. Cancellation kills the child process. Tenant stop is tenant-scoped. |
| 6 Controlled publishing | implemented against fixture GitHub | Publisher creates blob/tree/commit and advances the branch (`tests/integration/test_publish_flow.py`). Admission rereads installation, policy version, and approval-bound fingerprints. Publication locks persist in the database. |
| 7 Operations and quality | scaffolding + local drills | Alembic uses an async-safe engine. Compose starts API (0.0.0.0), optional Temporal worker, and web. Helm overrides the image command. Terraform defines S3, RDS, and IAM. Backup/restore scripts are exercised. Eval uses the fixture agent, not a silent `EXPECTED.patch` shortcut. |

## Definition of done (scoped pilot)

1. Working API, dashboard, workflow, agent, executor, verifier, publisher — yes for embedded adapters.
2. `python scripts/tf.py demo` owned-repo journey with real pytest — yes (simulated agent, labeled).
3. OpenAPI, migrations, architecture, threat model — yes.
4. Compose/Helm/Terraform, backup/restore, fail-closed sandbox admission — yes as code; production gVisor/CNI **not executed** on this workstation.
5. Unit/integration/security/e2e/chaos tests — yes, including the audit's reproduced failures.
6. Owned evals with cheating patches recorded as blocked — yes. Not 50 licensed tasks. Numbers are fixture-agent results, not live-model quality.
7. Metrics, Grafana JSON, runbooks, retention, audit export, tenant emergency stop — yes.
8. Demo: fail → reproduce → patch → verify → approve → draft PR with a repaired commit — yes against FixtureGitHub.

## Still environment-blocked

- Live GitHub App credentials and a real draft PR on github.com.
- gVisor `runsc` RuntimeClass / CNI deny-list on the dedicated Linux pool.
- PostgreSQL RLS runtime-role tests with `tracefix_app` NOSUPERUSER NOBYPASSRLS.
- Temporal cluster beyond the Compose profile.
- Measured SLO / uptime numbers.
- Held-out live-model evaluation (requires `ANTHROPIC_API_KEY` or `XAI_API_KEY` and a held-out split).
