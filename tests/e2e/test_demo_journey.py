from pathlib import Path
from uuid import uuid4

from tracefix.api.deps import AppContext
from tracefix.api.seed import REPO_ID, TENANT_A
from tracefix.domain.states import RepairRunState
from tracefix.orchestrator.runner import run_investigation
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.storage.models import RepairRun
from tracefix._paths import ROOT

TASK = ROOT / "evals" / "tasks" / "tf001-off-by-one"


async def test_owned_failure_reaches_approval(ctx: AppContext, tmp_path: Path):
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
            logical_key=f"e2e-{uuid4()}",
            simulated=True,
        )
        session.add(run)
        await session.commit()
        run_id = run.id
    result = await run_investigation(
        ctx.runtime,
        run_id,
        snapshot=TASK,
        policy=DEFAULT_POLICY,
        traceback="FAILED tests/test_stats.py::test_average",
    )
    assert result.state == RepairRunState.AWAITING_APPROVAL.value
    assert result.simulated is True
