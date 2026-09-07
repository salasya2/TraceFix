from httpx import ASGITransport, AsyncClient

from tracefix.api.app import create_app
from tracefix.api.deps import AppContext
from tracefix.api.seed import TENANT_A
from tracefix.domain.states import RepairRunState
from tracefix.storage.models import RepairRun


async def test_tenant_b_cannot_read_tenant_a(ctx: AppContext):
    async with ctx.sessions() as session:
        run = RepairRun(
            tenant_id=TENANT_A,
            repository_id=__import__("tracefix.api.seed", fromlist=["REPO_ID"]).REPO_ID,
            github_run_id=9,
            github_attempt=1,
            installation_github_id=9001,
            source_sha="a",
            base_sha="a",
            execution_sha="a",
            state=RepairRunState.RECEIVED.value,
            policy_version=1,
            workflow_id="w",
            logical_key="iso-1",
        )
        session.add(run)
        await session.commit()
        run_id = run.id
    app = create_app(ctx)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get(f"/v1/repair-runs/{run_id}", headers={"authorization": "Bearer other@tracefix.local"})
        assert denied.status_code == 404
        listed = await client.get("/v1/repair-runs", headers={"authorization": "Bearer other@tracefix.local"})
        assert listed.status_code == 200
        assert listed.json()["items"] == []
        ok = await client.get(f"/v1/repair-runs/{run_id}", headers={"authorization": "Bearer maintainer@tracefix.local"})
        assert ok.status_code == 200
