# Stuck workflow

1. Read the run timeline (`GET /v1/repair-runs/{id}`). Temporal history is the orchestration authority when `TRACEFIX_ORCHESTRATOR=temporal`.
2. If an Activity is retrying a non-retryable policy error, cancel the run.
3. Sweep sandboxes (`ExecutionBroker.sweep`) independently of the worker.
4. Re-dispatch pending outbox rows; the workflow ID is stable, so a second start is a join not a duplicate.
