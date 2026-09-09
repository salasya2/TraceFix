from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from tracefix.api.app import create_app
from tracefix.api.deps import AppContext
from tracefix.api.seed import REPO_ID, TENANT_A
from tracefix.domain.states import RepairRunState
from tracefix.orchestrator.runner import run_investigation
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.storage.models import RepairRun
from tracefix._paths import ROOT

TASK = ROOT / "evals" / "tasks" / "tf001-off-by-one"


async def test_approve_and_publish_opens_one_draft_pr(ctx: AppContext):
    async with ctx.sessions() as session:
        run = RepairRun(
            tenant_id=TENANT_A,
            repository_id=REPO_ID,
            github_run_id=1001,
            github_attempt=1,
            installation_github_id=9001,
            source_sha="deadbeefcafebabe",
            base_sha="deadbeefcafebabe",
            execution_sha="deadbeefcafebabe",
            state=RepairRunState.RECEIVED.value,
            policy_version=1,
            workflow_id=f"w-{uuid4()}",
            logical_key=f"pub-{uuid4()}",
            simulated=True,
        )
        session.add(run)
        await session.commit()
        run_id = run.id
    await run_investigation(
        ctx.runtime, run_id, snapshot=TASK, policy=DEFAULT_POLICY, traceback="fail"
    )
    app = create_app(ctx)
    transport = ASGITransport(app=app)
    headers = {"authorization": "Bearer maintainer@tracefix.local"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        detail = (await client.get(f"/v1/repair-runs/{run_id}")).json()
        cand = detail["candidates"][0]
        assert cand["verified"] is True
        approved = await client.post(
            f"/v1/candidates/{cand['id']}/approve", json={"patch_digest": cand["patch_digest"]}
        )
        assert approved.status_code == 200
        published = await client.post(f"/v1/candidates/{cand['id']}/publish")
        assert published.status_code == 200, published.text
        body = published.json()
        assert body["mode"] == "draft_pr"
        assert body["pr_number"] == 1
        repo = ctx.github._repo("acme", "stats")
        branch = body["branch"]
        ref = repo.refs.get(f"refs/heads/{branch}")
        assert ref is not None
        assert ref != "deadbeefcafebabe"
        assert repo.blobs, "publisher must create blobs for the repaired tree"
        assert any(isinstance(v, dict) and "parents" in v for v in repo.commits.values())
        again = await client.post(f"/v1/candidates/{cand['id']}/publish")
        assert again.json()["pr_number"] == 1
        denied = await client.get(
            f"/v1/repair-runs/{run_id}", headers={"authorization": "Bearer other@tracefix.local"}
        )
        assert denied.status_code == 404
