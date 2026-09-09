from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from tracefix.api.deps import AppContext, Maintainer, Viewer, get_ctx, get_session
from tracefix.api.serializers import CandidateOut, EventOut, RepairRunOut
from tracefix.domain.roles import MAINTAINER_ROLES
from tracefix.domain.states import RepairRunState
from tracefix.storage.models import Approval, Candidate, RepairRun, RepairRunEvent, VerificationRecord

router = APIRouter()


class ManualRunBody(BaseModel):
    github_run_id: int
    github_attempt: int = 1
    source_sha: str
    execution_sha: str
    base_sha: str | None = None


def _run_out(run: RepairRun) -> RepairRunOut:
    return RepairRunOut(
        id=run.id,
        state=run.state,
        reason_code=run.reason_code,
        reason_detail=run.reason_detail,
        source_sha=run.source_sha,
        base_sha=run.base_sha,
        execution_sha=run.execution_sha,
        simulated=run.simulated,
        cost_reserved_usd=run.cost_reserved_usd,
        cost_actual_usd=run.cost_actual_usd,
        diagnosis=run.diagnosis,
        limitations=run.limitations,
        github_run_id=run.github_run_id,
        github_attempt=run.github_attempt,
        created_at=run.created_at,
    )


@router.get("/v1/repair-runs")
async def list_runs(
    principal: Viewer,
    session: Annotated[AsyncSession, Depends(get_session)],
    state: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, le=100),
) -> dict:
    stmt = select(RepairRun).where(RepairRun.tenant_id == principal.tenant_id).order_by(RepairRun.created_at.desc())
    if state:
        stmt = stmt.where(RepairRun.state == state)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return {"items": [_run_out(r) for r in rows], "next_cursor": None}


@router.get("/v1/repair-runs/{run_id}")
async def get_run(
    run_id: UUID,
    principal: Viewer,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    run = await session.get(RepairRun, run_id)
    if run is None or run.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "run not found"})
    events = (
        (
            await session.execute(
                select(RepairRunEvent)
                .where(RepairRunEvent.run_id == run.id, RepairRunEvent.tenant_id == principal.tenant_id)
                .order_by(RepairRunEvent.at)
            )
        )
        .scalars()
        .all()
    )
    candidates = (
        (
            await session.execute(
                select(Candidate).where(Candidate.run_id == run.id, Candidate.tenant_id == principal.tenant_id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "run": _run_out(run),
        "events": [EventOut(state=e.state, actor=e.actor, reason=e.reason, detail=e.detail, at=e.at) for e in events],
        "candidates": [
            CandidateOut(
                id=c.id,
                iteration=c.iteration,
                patch_digest=c.patch_digest,
                verified=c.verified,
                badge=c.badge,
                changed_files=c.changed_files or [],
                validation_errors=c.validation_errors or [],
                model=c.model,
            )
            for c in candidates
        ],
    }


@router.post("/v1/repair-runs/{run_id}/cancel")
async def cancel_run(
    run_id: UUID,
    principal: Maintainer,
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    run = await session.get(RepairRun, run_id)
    if run is None or run.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "run not found"})
    if run.state not in {RepairRunState.CANCELLED.value}:
        run.state = RepairRunState.CANCELLED.value
        run.reason_code = "CANCELLED_BY_USER"
        session.add(
            RepairRunEvent(
                tenant_id=run.tenant_id,
                run_id=run.id,
                state=run.state,
                actor=principal.email,
                reason="CANCELLED_BY_USER",
            )
        )
        await ctx.runtime.broker.terminate_run(str(run.id))
    await session.commit()
    return {"id": str(run.id), "state": run.state}


@router.post("/v1/repair-runs/{run_id}/retry")
async def retry_run(
    run_id: UUID,
    principal: Maintainer,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    parent = await session.get(RepairRun, run_id)
    if parent is None or parent.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "run not found"})
    child = RepairRun(
        tenant_id=parent.tenant_id,
        repository_id=parent.repository_id,
        github_run_id=parent.github_run_id,
        github_attempt=parent.github_attempt,
        installation_github_id=parent.installation_github_id,
        source_sha=parent.source_sha,
        base_sha=parent.base_sha,
        execution_sha=parent.execution_sha,
        state=RepairRunState.RECEIVED.value,
        policy_version=parent.policy_version,
        workflow_id=f"repair-{uuid4()}",
        parent_run_id=parent.id,
        logical_key=parent.logical_key + f":retry:{uuid4()}",
        simulated=parent.simulated,
    )
    session.add(child)
    await session.commit()
    return {"id": str(child.id), "parent_id": str(parent.id)}


@router.get("/v1/repair-runs/{run_id}/events")
async def stream_events(
    run_id: UUID,
    principal: Viewer,
    session: Annotated[AsyncSession, Depends(get_session)],
    cursor: int = 0,
):
    run = await session.get(RepairRun, run_id)
    if run is None or run.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "run not found"})

    async def gen():
        events = (
            (
                await session.execute(
                    select(RepairRunEvent)
                    .where(RepairRunEvent.run_id == run_id, RepairRunEvent.tenant_id == principal.tenant_id)
                    .order_by(RepairRunEvent.at)
                )
            )
            .scalars()
            .all()
        )
        for idx, event in enumerate(events):
            if idx < cursor:
                continue
            yield {
                "id": str(idx),
                "data": event.state,
            }

    return EventSourceResponse(gen())
