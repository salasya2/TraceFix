from uuid import uuid4

from sqlalchemy import select

from tracefix.api.deps import AppContext
from tracefix.api.seed import REPO_ID, TENANT_A
from tracefix.domain.states import RepairRunState
from tracefix.orchestrator.outbox import dispatch_outbox
from tracefix.storage.models import OutboxEvent, RepairRun
from tracefix._paths import ROOT


async def test_outbox_dispatch_runs_investigation(ctx: AppContext):
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
            workflow_id=f"wf-{uuid4()}",
            logical_key=f"outbox-{uuid4()}",
            simulated=True,
        )
        session.add(run)
        await session.flush()
        session.add(
            OutboxEvent(
                tenant_id=TENANT_A,
                topic="repair.start",
                payload={"run_id": str(run.id)},
                workflow_id=run.workflow_id,
            )
        )
        await session.commit()
        run_id = run.id
    n = await dispatch_outbox(
        ctx.sessions,
        ctx.runtime,
        ctx.github,
        fixture_root=ROOT / "evals" / "tasks" / "tf001-off-by-one",
    )
    assert n == 1
    async with ctx.sessions() as session:
        run = await session.get(RepairRun, run_id)
        assert run.state in {
            RepairRunState.AWAITING_APPROVAL.value,
            RepairRunState.NO_VALID_PATCH.value,
        }
        leftover = (
            await session.execute(select(OutboxEvent).where(OutboxEvent.dispatched_at.is_(None)))
        ).scalars().all()
        assert leftover == []
