# ADR 0004 — Draft PRs are privileged side effects

## Decision

Publication uses a lock on `(tenant, repository, workflow_run_id, attempt)`. Approval is bound to patch digest, SHAs, policy version, evidence id, approver, and TTL. If workflow safety cannot be established, use patch-download mode.

The publisher never asks the model to regenerate a patch after verification and never force-pushes.

## Alternatives

- Auto-merge: deferred until a separate design exists.
- Rebase onto a moved base: mark stale and re-verify.
