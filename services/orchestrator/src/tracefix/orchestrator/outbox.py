from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tracefix.github.snapshot import materialize_fixture_snapshot
from tracefix.orchestrator.runner import InvestigationRuntime, run_investigation
from tracefix.policy.schema import DEFAULT_POLICY, RepositoryPolicy
from tracefix.storage.models import OutboxEvent, RepairRun, Repository, RepositoryPolicyRow

CLAIM_TTL = timedelta(minutes=15)


async def dispatch_outbox(
    sessions: async_sessionmaker[AsyncSession],
    runtime: InvestigationRuntime,
    github,
    *,
    fixture_root: Path | None = None,
    start_workflow=None,
) -> int:
    dispatched = 0
    now = datetime.now(timezone.utc)
    stale_before = now - CLAIM_TTL
    async with sessions() as session:
        pending = (
            (
                await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.dispatched_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                )
            )
            .scalars()
            .all()
        )
        claimable = [
            event
            for event in pending
            if event.claimed_at is None or event.claimed_at.replace(tzinfo=timezone.utc) < stale_before
        ]
        if not claimable:
            return 0
        event = claimable[0]
        event.claimed_at = now
        event.attempts = (event.attempts or 0) + 1
        await session.commit()
        event_id = event.id
        payload = dict(event.payload or {})
        workflow_id = event.workflow_id

    run_id = UUID(payload["run_id"])
    async with sessions() as session:
        run = await session.get(RepairRun, run_id)
        if run is None:
            async with sessions() as mark:
                row = await mark.get(OutboxEvent, event_id)
                if row:
                    row.dispatched_at = datetime.now(timezone.utc)
                    await mark.commit()
            return 1
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

    try:
        if start_workflow is not None:
            await start_workflow(
                {
                    "run_id": str(run_id),
                    "snapshot": str(snap_dest),
                    "policy": policy.dump(),
                    "traceback": traceback or "FAILED",
                    "workflow_id": workflow_id,
                }
            )
        else:
            await run_investigation(
                runtime,
                run_id,
                snapshot=snap_dest,
                policy=policy,
                traceback=traceback or "FAILED",
            )
    except Exception:
        async with sessions() as session:
            row = await session.get(OutboxEvent, event_id)
            if row and row.dispatched_at is None:
                row.claimed_at = None
                await session.commit()
        raise

    async with sessions() as session:
        row = await session.get(OutboxEvent, event_id)
        if row:
            row.dispatched_at = datetime.now(timezone.utc)
            await session.commit()
    return dispatched + 1


async def run_dispatcher_loop(sessions, runtime, github, *, fixture_root: Path | None = None, interval: float = 2.0) -> None:
    import asyncio

    while True:
        try:
            await dispatch_outbox(sessions, runtime, github, fixture_root=fixture_root)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(interval)
