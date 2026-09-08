# Model regression

Freeze `TRACEFIX_PROMPT_VERSION` and `TRACEFIX_MODEL_ID`. Roll forward with a canary tenant. Compare `artifacts/evaluation.json` against the previous report. Roll back by pinning the previous prompt version and model ID; workflow code changes require Temporal versioning.
