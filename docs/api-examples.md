# API examples

All mutations that go through the browser use the `tracefix_session` cookie. Tests and CLIs may send `Authorization: Bearer maintainer@tracefix.local` in `TRACEFIX_AUTH_MODE=dev`.

## Login

```http
POST /v1/auth/login
{"email": "maintainer@tracefix.local"}
```

## Webhook

```http
POST /webhooks/github
X-Hub-Signature-256: sha256=...
X-GitHub-Delivery: 1
X-GitHub-Event: workflow_run
```

Invalid signatures return 401. Duplicate delivery IDs collapse. Duplicate logical keys collapse.

## Investigate, review, publish

```http
GET  /v1/repair-runs
GET  /v1/repair-runs/{id}
GET  /v1/candidates/{id}
POST /v1/candidates/{id}/approve  {"patch_digest": "..."}
POST /v1/candidates/{id}/publish
GET  /v1/audit-events/export
POST /v1/organization/emergency-stop {"engaged": true}
```

Structured errors: `{ "code", "message", "request_id", "retryable" }`.
