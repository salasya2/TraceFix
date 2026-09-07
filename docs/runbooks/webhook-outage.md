# Webhook outage

1. Confirm `/health` and signature rejects in API logs (no raw payloads).
2. GitHub does not automatically redeliver failed deliveries — run the reconciler cursor over workflow runs.
3. Dedup is by delivery ID **and** logical key `(installation, repo, run, attempt, policy version, execution SHA)`.
4. If the outbox dispatcher crashed after commit, the stable workflow ID recovers the existing workflow.
