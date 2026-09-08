# Tenant suspension

`POST /v1/organization/emergency-stop` sets `tenants.status=suspended` and `emergency_stop`. The executor stop switch refuses new jobs. Publisher refuses write tokens. Existing sandboxes are swept.
