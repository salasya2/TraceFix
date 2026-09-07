# ADR 0001 — Monorepo with separated deployment identities

## Decision

One monorepo. Shared schemas in `packages/*`. Separate deployable identities for API, orchestrator, executor, publisher, and credential broker.

## Rationale

Credentials and hostile execution require process and network boundaries. Sharing a git repo does not share a service identity.

## Alternatives

- Multi-repo: slower contract evolution for a pilot.
- Single process for everything: faster demo, unacceptable for untrusted pytest.
