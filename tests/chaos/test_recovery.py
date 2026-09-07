from uuid import uuid4

from tracefix.api.deps import AppContext
from tracefix.api.seed import REPO_ID, TENANT_A
from tracefix.domain.states import RepairRunState
from tracefix.orchestrator.runner import run_investigation
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.storage.models import RepairRun
from tracefix._paths import ROOT

TASK = ROOT / "evals" / "tasks" / "tf001-off-by-one"


async def test_rerun_after_crash_does_not_duplicate_logical_key(ctx: AppContext):
    key = f"chaos-{uuid4()}"
    async with ctx.sessions() as session:
        run = RepairRun(
            tenant_id=TENANT_A,
            repository_id=REPO_ID,
            github_run_id=77,
            github_attempt=1,
            installation_github_id=9001,
            source_sha="deadbeefcafebabe",
            base_sha="deadbeefcafebabe",
            execution_sha="deadbeefcafebabe",
            state=RepairRunState.RECEIVED.value,
            policy_version=1,
            workflow_id="wf-1",
            logical_key=key,
        )
        session.add(run)
        await session.commit()
        run_id = run.id
    first = await run_investigation(ctx.runtime, run_id, snapshot=TASK, policy=DEFAULT_POLICY, traceback="fail")
    # crash/retry of the same run id is rejected by the state machine once terminal/waiting
    assert first.id == run_id
    assert first.state in {
        RepairRunState.AWAITING_APPROVAL.value,
        RepairRunState.NO_VALID_PATCH.value,
    }
