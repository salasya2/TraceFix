# Orphan sandbox

The lifecycle sweeper (`ExecutionBroker.sweep`) is independent of Temporal worker health.

1. List leases past expiry.
2. Terminate process trees / `docker rm -f`.
3. Record `cleanup_at`.
4. Tenant emergency stop prevents new work while cleanup proceeds.

Target: expired sandbox cleanup within five minutes, including worker-crash cases. Measure this on the production pool before citing it.
