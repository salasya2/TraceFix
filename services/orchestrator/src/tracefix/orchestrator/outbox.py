from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tracefix.github.fixture import FixtureGitHub
from tracefix.github.snapshot import materialize_fixture_snapshot
from tracefix.orchestrator.runner import InvestigationRuntime, run_investigation
from tracefix.policy.schema import DEFAULT_POLICY, RepositoryPolicy
from tracefix.storage.models import OutboxEvent, RepairRun, Repository, RepositoryPolicyRow


async def dispatch_outbox(
    sessions: async_sessionmaker[AsyncSession],
    runtime: InvestigationRuntime,
    github: FixtureGitHub,
    *,
    fixture_root: Path | None = None,
) -> int:
    dispatched = 0
    async with sessions() as session:
        pending = (
            (
                await session.execute(
                    select(OutboxEvent).where(OutboxEvent.dispatched_at.is_(None)).order_by(OutboxEvent.created_at)
                )
            )
            .scalars()
            .all()
        )
        for event in pending:
            run_id = UUID(event.payload["run_id"])
            run = await session.get(RepairRun, run_id)
            if run is None:
                event.dispatched_at = datetime.now(timezone.utc)
                continue
            repo = await session.get(Repository, run.repository_id)
            policy_row = (
                await session.execute(
                    select(RepositoryPolicyRow)
                    .where(RepositoryPolicyRow.repository_id == repo.id)
                    .order_by(RepositoryPolicyRow.version.desc())
                )
            ).scalars().first()
            policy = RepositoryPolicy.model_validate(policy_row.document) if policy_row else DEFAULT_POLICY
            owner, name = repo.full_name.split("/", 1)
            snap_dest = runtime.work_root / str(run.id) / "fetched"
            if fixture_root and fixture_root.exists():
                import shutil

                snap_dest.parent.mkdir(parents=True, exist_ok=True)
                if snap_dest.exists():
                    shutil.rmtree(snap_dest)
                shutil.copytree(fixture_root, snap_dest)
            else:
                await materialize_fixture_snapshot(github, owner, name, run.execution_sha, snap_dest)
            traceback = ""
            try:
                traceback = await github.get_run_logs(owner, name, run.github_run_id, attempt=run.github_attempt)
            except Exception:
                traceback = "missing logs"
            event.dispatched_at = datetime.now(timezone.utc)
            await session.commit()
            await run_investigation(
                runtime,
                run.id,
                snapshot=snap_dest,
                policy=policy,
                traceback=traceback or "FAILED",
            )
            dispatched += 1
    return dispatched
