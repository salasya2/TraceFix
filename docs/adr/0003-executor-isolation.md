# ADR 0003 — Executor adapters and fail-closed production runtime

## Decision

`ExecutionBroker` accepts only signed job specs. Local backend: process or ordinary Docker. Production backend: gVisor `runsc` RuntimeClass. If the sandbox runtime or network enforcement is unavailable, admission fails closed. Never silently fall back to runc in production.

## Rationale

Ordinary Docker is a developer convenience. gVisor reduces host kernel exposure but still needs a surrounding architecture (no credentials in the guest, no egress, external lifecycle sweeper).
