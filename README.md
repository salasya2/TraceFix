# TraceFix

Investigate a failed GitHub Actions run, reproduce a supported Python defect, propose a small patch, independently verify it, and prepare an approval-gated draft pull request.

This repository is a scoped pilot. Architecture, limits, and operational targets in the [build specification](docs/SPEC.md) are design choices and release targets, not production SLAs.

## What it does

1. A GitHub App webhook authenticates a failed workflow run.
2. TraceFix admits the event, snapshots the exact execution revision, and reproduces the failure.
3. A constrained agent inspects authorized source and submits a bounded patch.
4. A **separate** verifier applies that patch to a fresh snapshot and re-runs the approved pytest profile.
5. A maintainer reviews diagnosis, diff, evidence, cost, and limitations, then approves a digest-bound candidate.
6. The publisher opens a draft PR **or** returns a downloadable patch when workflow safety cannot be established.

## Repository layout

Matches the enterprise build specification: `apps/api`, `apps/web`, `services/*`, `packages/*`, `evals/`, `tests/`, `deploy/`, `infra/`, `docs/`.

## Prerequisites (verified on this workstation)

| Tool | Version used during bootstrap |
|---|---|
| Python | 3.13.7 (profiles target 3.12–3.13) |
| uv | 0.8.11 |
| Node.js | 22.12.0 |
| pnpm | 10.34.5 |
| Docker | 28.0.1 |
| GitHub API version | 2022-11-28 |
| Default real model | `grok-4.5` via SpaceXAI (`XAI_API_KEY`) |

Windows: run local orchestration under WSL2/Linux for production-like Docker isolation. The embedded demo uses a process executor and works on Windows.

## Commands

`Taskfile.yml` is the documented interface. This checkout also ships `python scripts/tf.py`, which implements the same verbs (go-task is optional).

```text
python scripts/tf.py bootstrap
python scripts/tf.py demo
python scripts/tf.py test unit
python scripts/tf.py test integration
python scripts/tf.py test security
python scripts/tf.py test e2e
python scripts/tf.py lint
python scripts/tf.py eval --split development --output artifacts/evaluation.json
```

`demo` runs the owned `tf001-off-by-one` fixture through the real API workflow, executor, verifier, and dashboard data path. The fixture agent is **labeled simulated**. Verification still executes pytest twice on the baseline and once on a fresh patched copy.

## Local profiles

- `TRACEFIX_PROFILE=embedded` (default): SQLite, local disk artifacts, in-process runner, process executor, fixture GitHub.
- `TRACEFIX_PROFILE=compose`: PostgreSQL 17, MinIO, Temporal, API, worker, web — see `deploy/local/docker-compose.yml`.
- Production: gVisor RuntimeClass on a dedicated execution pool. Ordinary Docker is **not** the hostile-code boundary.

## Security boundaries

- Webhook HMAC is verified on the raw body before JSON parsing.
- Models cannot run shell, mint credentials, or publish.
- Fetcher/orchestrator identities cannot mint write tokens.
- Publication is digest-bound, lock-keyed per logical run attempt, and fails closed when workflow safety is unknown.
- Row-level security is defined for PostgreSQL; the application also filters every query by `tenant_id`.

## What is not claimed

gVisor containment, 99.9% API availability, and live GitHub App publication are not marked passing until those environments are executed. Local Docker tests do not demonstrate production isolation.
