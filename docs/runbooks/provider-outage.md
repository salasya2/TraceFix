# Model provider outage

Preserve existing budget reservations. Do not assume a timed-out Activity was free.

Switch `TRACEFIX_MODEL_PROVIDER=fixture` only in development. Production should fail the run as `PROVIDER_UNAVAILABLE` (retryable) within the investigation budget.
