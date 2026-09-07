# Unsafe publication

If a privileged `pull_request_target` or `workflow_run` path can execute candidate code with secrets:

1. Set the repository to `publication_mode=patch_download`.
2. Invalidate the safety fingerprint.
3. Do not open a branch.
4. Rotate any token that may have been exposed.
5. Export the audit chain (`GET /v1/audit-events`).
