from __future__ import annotations

import json

from httpx import ASGITransport, AsyncClient

from tracefix.api.app import create_app
from tracefix.api.deps import AppContext
from tracefix.github.signature import sign_body


def _payload() -> bytes:
    return json.dumps(
        {
            "action": "completed",
            "workflow_run": {
                "id": 1001,
                "head_sha": "deadbeefcafebabe",
                "event": "push",
                "status": "completed",
                "conclusion": "failure",
                "run_attempt": 1,
                "head_branch": "main",
                "workflow_id": 7,
                "name": "tests",
            },
            "repository": {"id": 4242, "full_name": "acme/stats", "fork": False, "default_branch": "main"},
            "installation": {"id": 9001, "account": {"login": "acme"}},
        }
    ).encode()


async def test_forged_rejected_and_duplicates_collapse(ctx: AppContext):
    app = create_app(ctx)
    body = _payload()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        bad = await client.post(
            "/webhooks/github",
            content=body,
            headers={
                "x-hub-signature-256": "sha256=00",
                "x-github-event": "workflow_run",
                "x-github-delivery": "d0",
                "content-type": "application/json",
            },
        )
        assert bad.status_code == 401
        secret = ctx.settings.github_webhook_secret
        header = sign_body(secret=secret, body=body)
        run_ids = set()
        for i in range(100):
            res = await client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "x-hub-signature-256": header,
                    "x-github-event": "workflow_run",
                    "x-github-delivery": f"dup-{i}",
                    "content-type": "application/json",
                },
            )
            assert res.status_code == 200
            data = res.json()
            if data.get("run_id"):
                run_ids.add(data["run_id"])
        assert len(run_ids) == 1
