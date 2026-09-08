# Canary and rollback

- Model, prompt, harness, and policy-engine changes roll out to a canary tenant first.
- Preserve versioned container digests. Helm `image.digest` is required; `latest` is forbidden.
- Database migrations are expand/contract. Do not drop columns in the same release that stops writing them.
- Temporal workflow code changes must remain replay-compatible with recorded histories.
- Rollback: helm rollback to the previous digest, restore `TRACEFIX_PROMPT_VERSION`, do not replay unverified patches onto a moved base.
