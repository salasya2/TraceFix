# Threat model (pilot)

## Assets

- GitHub App private key and installation tokens
- Tenant source snapshots and logs
- Model prompts containing private code
- Publication ability (branch + draft PR)

## Actors

- External webhook sender
- Onboarded maintainer
- Malicious repository content / pytest code
- Compromised model output
- Neighbor tenant

## Controls

| Threat | Control |
|---|---|
| Forged webhook | HMAC-SHA256 on raw body, constant-time compare |
| Cross-tenant read | `tenant_id` on every query; Postgres RLS USING + WITH CHECK |
| Prompt injection | Typed tools only; server-side authz; no shell/network/credentials |
| Sandbox breakout | Non-root, no egress, no credentials, external sweeper; gVisor in production |
| Cheating patch | Protected paths, skip/harness detectors, inventory comparison, human approval |
| Duplicate PR | Publication lock + reconcile existing PR by head branch |
| Token theft via logs | Tokens never logged, never mounted into guests, never sent to the model |

## Out of scope for v1

Windows/macOS reproduction, fork PRs, lockfile repair, auto-merge, arbitrary languages.
