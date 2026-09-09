from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from tracefix._paths import ROOT
from tracefix.api.app import create_app
from tracefix.api.deps import AppContext
from tracefix.api.seed import REPO_ID, TENANT_A, principals, seed_world
from tracefix.domain.contracts import LogicalRunKey
from tracefix.domain.states import RepairRunState
from tracefix.github.fixture import FixtureGitHub
from tracefix.orchestrator.runner import InvestigationRuntime, run_investigation
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.settings import Settings
from tracefix.storage.artifacts import ArtifactStore
from tracefix.storage.engine import create_engine_from_url, create_session_factory, init_schema
from tracefix.storage.models import Candidate, RepairRun, RepairRunEvent


def fixture_task() -> Path:
    return ROOT / "evals" / "tasks" / "tf001-off-by-one"


async def build_context() -> AppContext:
    settings = Settings(
        env="development",
        auth_mode="dev",
        profile="embedded",
        executor="process",
        model_provider="fixture",
        orchestrator="local",
        allow_insecure_executor=True,
    )
    settings.database_url = "sqlite+aiosqlite:///" + str(ROOT / ".data" / "tracefix.db")
    engine = create_engine_from_url(settings.database_url)
    await init_schema(engine)
    sessions = create_session_factory(engine)
    artifacts = ArtifactStore(ROOT / ".data" / "artifacts")
    github = FixtureGitHub()
    await seed_world(sessions, github, fixture_task())
    runtime = InvestigationRuntime(sessions=sessions, artifacts=artifacts, work_root=ROOT / ".data" / "work")
    return AppContext(
        settings=settings,
        sessions=sessions,
        runtime=runtime,
        github=github,
        seed_principals=principals(),
    )


async def run_demo(*, serve: bool = False) -> int:
    ctx = await build_context()
    snapshot = fixture_task()
    traceback = (
        "tests/test_stats.py:6: in test_average\n"
        "    assert average([2, 4]) == 3\n"
        "E   assert 6.0 == 3\n"
        "src/stats.py:4: in average\n"
        "    return sum(nums) / (len(nums) - 1)\n"
    )
    logical = LogicalRunKey(
        installation_id=9001,
        repository_id=4242,
        workflow_run_id=1001,
        run_attempt=1,
        policy_version=1,
        execution_sha="deadbeefcafebabe",
    )
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
            workflow_id=f"repair-{uuid4()}",
            logical_key=f"{logical.encode()}:demo:{uuid4()}",
            simulated=True,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    run = await run_investigation(
        ctx.runtime,
        run_id,
        snapshot=snapshot,
        policy=DEFAULT_POLICY,
        traceback=traceback,
    )
    async with ctx.sessions() as session:
        events = (
            await session.execute(select(RepairRunEvent).where(RepairRunEvent.run_id == run_id))
        ).scalars().all()
        cands = (await session.execute(select(Candidate).where(Candidate.run_id == run_id))).scalars().all()
        print("=== TraceFix demo ===")
        print(f"run:        {run.id}")
        print(f"state:      {run.state}")
        print(f"reason:     {run.reason_code}")
        print(f"simulated:  {run.simulated} (fixture provider labeled)")
        print(f"candidates: {len(cands)} verified={any(c.verified for c in cands)}")
        print("timeline:")
        for event in events:
            print(f"  {event.state:24} {event.actor:14} {event.reason}")
        if run.diagnosis:
            print("diagnosis:", json.dumps(run.diagnosis, indent=2)[:800])

    app = create_app(ctx, start_dispatcher=serve)
    if serve:
        import uvicorn

        print("API listening on http://127.0.0.1:8080")
        print("Dashboard expects Vite on http://127.0.0.1:5173")
        print(f"Open run http://127.0.0.1:5173/runs/{run.id}")
        config = uvicorn.Config(app, host="127.0.0.1", port=8080, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    return 0 if run.state in {RepairRunState.AWAITING_APPROVAL.value, RepairRunState.PR_OPENED.value} else 1
