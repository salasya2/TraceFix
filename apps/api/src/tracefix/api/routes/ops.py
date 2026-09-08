from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracefix.api.deps import Admin, AppContext, Viewer, get_ctx, get_session
from tracefix.api.metrics import scrape
from tracefix.storage.audit import record_audit
from tracefix.storage.models import AuditEvent, Tenant
from tracefix.storage.retention import apply_retention, suspend_tenant

router = APIRouter()


class EmergencyBody(BaseModel):
    engaged: bool = True


@router.post("/v1/organization/emergency-stop")
async def emergency_stop(
    body: EmergencyBody,
    principal: Admin,
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    tenant = await session.get(Tenant, principal.tenant_id)
    if tenant:
        tenant.emergency_stop = body.engaged
        if body.engaged:
            tenant.status = "suspended"
    ctx.runtime.broker.emergency_stop = body.engaged
    if body.engaged:
        ctx.runtime.broker.tenant_stops.add(str(principal.tenant_id))
        await suspend_tenant(session, principal.tenant_id)
    await record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor=principal.email,
        action="emergency_stop",
        target_type="tenant",
        target_id=str(principal.tenant_id),
        payload={"engaged": body.engaged},
    )
    await session.commit()
    return {"emergency_stop": body.engaged}


@router.get("/v1/audit-events/export")
async def export_audit(principal: Viewer, session: Annotated[AsyncSession, Depends(get_session)]) -> Response:
    rows = (
        (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.tenant_id == principal.tenant_id)
                .order_by(AuditEvent.at)
            )
        )
        .scalars()
        .all()
    )
    payload = [
        {
            "id": str(r.id),
            "actor": r.actor,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "at": r.at.isoformat() if r.at else None,
            "digest": r.digest,
            "prev_digest": r.prev_digest,
            "payload": r.payload,
        }
        for r in rows
    ]
    body = json.dumps({"exported_at": datetime.now(timezone.utc).isoformat(), "items": payload}, indent=2)
    return Response(content=body, media_type="application/json")


@router.post("/v1/ops/retention")
async def run_retention(
    principal: Admin,
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    result = await apply_retention(session, ctx.runtime.artifacts)
    await session.commit()
    return result


@router.get("/metrics")
async def metrics() -> Response:
    data, content_type = scrape()
    return Response(content=data, media_type=content_type)
