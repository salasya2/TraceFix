from httpx import ASGITransport, AsyncClient

from tracefix.api.app import create_app
from tracefix.api.deps import AppContext
from tracefix.settings import Settings, validate_startup


async def test_production_rejects_fixture_identities(ctx: AppContext):
    ctx.settings.env = "production"
    ctx.settings.auth_mode = "oidc"
    app = create_app(ctx)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        anon = await client.get("/v1/auth/me")
        assert anon.status_code == 401
        bearer = await client.get(
            "/v1/auth/me", headers={"authorization": "Bearer maintainer@tracefix.local"}
        )
        assert bearer.status_code == 401
        login = await client.post("/v1/auth/login", json={"email": "maintainer@tracefix.local"})
        assert login.status_code == 403


def test_production_dev_auth_refuses_to_start():
    settings = Settings()
    settings.env = "production"
    settings.auth_mode = "dev"
    settings.allow_insecure_executor = True
    try:
        validate_startup(settings)
        assert False, "expected startup rejection"
    except RuntimeError as exc:
        assert "TRACEFIX_AUTH_MODE=dev" in str(exc)
