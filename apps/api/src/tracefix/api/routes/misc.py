from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracefix.api.deps import AppContext, Viewer, get_ctx, get_session
from tracefix.storage.models import Artifact, AuditEvent, UsageLedger

router = APIRouter()


@router.get("/v1/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: UUID,
    principal: Viewer,
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    art = await session.get(Artifact, artifact_id)
    if art is None or art.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})
    data = ctx.runtime.artifacts.get(art.storage_key)
    text = data.decode("utf-8", "replace") if art.access_class != "raw" else "<redacted binary>"
    return {
        "id": str(art.id),
        "kind": art.kind,
        "sha256": art.sha256,
        "size": art.size,
        "content": text if art.access_class in {"redacted", "source"} else None,
    }


@router.get("/v1/usage")
async def usage(principal: Viewer, session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    rows = (
        (
            await session.execute(
                select(UsageLedger).where(UsageLedger.tenant_id == principal.tenant_id)
            )
        )
        .scalars()
        .all()
    )
    reserved = sum(r.amount_usd for r in rows if r.kind == "reservation")
    settled = sum(r.amount_usd for r in rows if r.kind == "settlement")
    return {"reserved_usd": reserved, "settled_usd": settled, "items": len(rows)}


@router.get("/v1/audit-events")
async def audit_events(principal: Viewer, session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    rows = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.tenant_id == principal.tenant_id)
                .order_by(AuditEvent.at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "actor": r.actor,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "at": r.at.isoformat() if r.at else None,
                "digest": r.digest,
            }
            for r in rows
        ]
    }


@router.get("/v1/overview")
async def overview(principal: Viewer, session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    from tracefix.storage.models import Candidate, RepairRun

    runs = (
        (await session.execute(select(RepairRun).where(RepairRun.tenant_id == principal.tenant_id)))
        .scalars()
        .all()
    )
    cands = (
        (await session.execute(select(Candidate).where(Candidate.tenant_id == principal.tenant_id)))
        .scalars()
        .all()
    )
    return {
        "active_runs": sum(1 for r in runs if r.state not in {"PR_OPENED", "CANCELLED", "NO_VALID_PATCH"}),
        "verified_candidates": sum(1 for c in cands if c.verified),
        "unsuccessful": sum(1 for r in runs if r.state in {"NO_VALID_PATCH", "UNREPRODUCIBLE", "FLAKY_SUSPECTED"}),
        "runs": len(runs),
    }
