from httpx import ASGITransport, AsyncClient

from tracefix.api.app import create_app
from tracefix.api.deps import AppContext


async def test_login_me_export_and_metrics(ctx: AppContext):
    app = create_app(ctx)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/v1/auth/login", json={"email": "maintainer@tracefix.local"})
        assert login.status_code == 200
        me = await client.get("/v1/auth/me", headers={"authorization": "Bearer maintainer@tracefix.local"})
        assert me.status_code == 200
        exported = await client.get(
            "/v1/audit-events/export", headers={"authorization": "Bearer maintainer@tracefix.local"}
        )
        assert exported.status_code == 200
        assert "items" in exported.json()
        metrics = await client.get("/metrics")
        assert metrics.status_code == 200
        assert b"tracefix_" in metrics.content or metrics.status_code == 200
