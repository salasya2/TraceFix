# TraceFix implementation progress

Updated: 2026-09-07

## Phase status

| Phase | Status | Evidence |
|---|---|---|
| 0 Contracts and threat model | complete | `docs/adr/*`, `docs/threat-model.md`, policy schema, fixture tasks |
| 1 Reproducible verifier | complete | `packages/verification`, `tests/integration/test_verification.py` |
| 2 Durable ingestion | complete (embedded) | webhook HMAC, delivery+logical dedup, outbox, SQLite/Postgres schema |
| 3 Constrained agent | complete | typed tools, fixture + SpaceXAI + Anthropic providers, cost reservation |
| 4 Maintainer product | complete (dev auth) | FastAPI + React dashboard, two seeded tenants, RLS SQL for Postgres |
| 5 Hostile execution | local adapter only | process + Docker adapters; gVisor not executed on this host |
| 6 Controlled publishing | complete against fixture GitHub | digest-bound approval, one draft PR per logical attempt, audit chain |
| 7 Operations and quality | partial | compose/helm/terraform, evals, runbooks; staging restore drill not executed |

## Verified on this host (2026-09-07)

- `uv run pytest -q` — 21 passed (unit, integration, security, e2e, chaos)
- `python scripts/tf.py demo` — tf001 reproduced, independently verified, `AWAITING_APPROVAL`
- Maintainer approve + publish — fixture draft PR `https://github.com/acme/stats/pull/1`, run state `PR_OPENED`
- Tenant B cannot read tenant A (HTTP 404)
- `eval --split development` — 7/7 owned tasks verified with publisher disabled
- Dashboard Vite on :5173 and API on :8080 served live data

## Unresolved / environment-blocked

- Live GitHub App private key and webhook secret are not present; fixture GitHub is used.
- PostgreSQL RLS runtime-role tests require a Postgres instance and `tracefix_app` role.
- gVisor `runsc` RuntimeClass and CNI deny-list tests require the Linux execution pool.
- OIDC/Keycloak path is implemented as configuration, not a live IdP in embedded mode.
- Temporal worker is defined; demo uses the in-process runner.

## Next vertical slice

1. `python scripts/tf.py bootstrap`
2. `python scripts/tf.py test all`
3. Point `XAI_API_KEY` at SpaceXAI and set `TRACEFIX_MODEL_PROVIDER=spacexai` for a live agent pass on `tf001`.
4. Bring up `deploy/local/docker-compose.yml` for Postgres + Temporal.
