# ADR 0002 — Temporal owns the durable state machine

## Decision

Temporal is the production orchestrator. Activities wrap GitHub, model, DB, and sandbox I/O. The embedded profile uses `InvestigationRuntime`, which executes the same activity sequence in-process against PostgreSQL/SQLite.

There is no second LangGraph state machine.

## Rationale

Replay and retries are not exactly-once. Idempotency keys and an outbox reconcile GitHub and publication side effects.

## Alternatives

- Homegrown Postgres queue: more code, weaker timers.
- LangGraph as system of record: conflicts with Temporal replay.
