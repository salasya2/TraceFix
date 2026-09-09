from uuid import uuid4

from sqlalchemy import select

from tracefix._paths import ROOT
from tracefix.api.deps import AppContext
from tracefix.api.seed import REPO_ID, TENANT_A
from tracefix.domain.states import RepairRunState
from tracefix.orchestrator.outbox import dispatch_outbox
from tracefix.storage.models import OutboxEvent, RepairRun

TASK = ROOT / "evals" / "tasks" / "tf001-off-by-one"


async def test_crash_before_dispatch_mark_retries_once(ctx: AppContext):
    ctx.runtime.crash_after = "admitted"
    async with ctx.sessions() as session:
        run = RepairRun(
            tenant_id=TENANT_A,
            repository_id=REPO_ID,
            github_run_id=88,
            github_attempt=1,
            installation_github_id=9001,
            source_sha="deadbeefcafebabe",
            base_sha="deadbeefcafebabe",
            execution_sha="deadbeefcafebabe",
            state=RepairRunState.RECEIVED.value,
            policy_version=1,
            workflow_id=f"wf-{uuid4()}",
            logical_key=f"crash-{uuid4()}",
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
    try:
        await dispatch_outbox(ctx.sessions, ctx.runtime, ctx.github, fixture_root=TASK)
        assert False, "expected injected crash"
    except RuntimeError as exc:
        assert "injected crash" in str(exc)
    async with ctx.sessions() as session:
        event = (await session.execute(select(OutboxEvent))).scalars().first()
        assert event.dispatched_at is None
        run = await session.get(RepairRun, run_id)
        assert run.state != RepairRunState.RECEIVED.value
    ctx.runtime.crash_after = None
    n = await dispatch_outbox(ctx.sessions, ctx.runtime, ctx.github, fixture_root=TASK)
    assert n == 1
    async with ctx.sessions() as session:
        run = await session.get(RepairRun, run_id)
        assert run.state == RepairRunState.AWAITING_APPROVAL.value
        leftover = (
            await session.execute(select(OutboxEvent).where(OutboxEvent.dispatched_at.is_(None)))
        ).scalars().all()
        assert leftover == []
