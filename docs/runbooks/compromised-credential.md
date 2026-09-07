# Compromised GitHub App credential

1. Rotate the App private key and webhook secret using the documented secret store.
2. Suspend the tenant (`tenants.status=suspended`) and engage emergency stop.
3. Sweeper tears down sandboxes; publisher refuses new write tokens.
4. Export audit digests to separately permissioned storage.
