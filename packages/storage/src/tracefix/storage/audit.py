from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracefix.storage.models import AuditEvent


async def record_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    payload: dict,
) -> AuditEvent:
    prev = (
        await session.execute(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    prev_digest = prev.digest if prev else None
    body = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "actor": actor,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload,
            "prev": prev_digest,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(body.encode()).hexdigest()
    event = AuditEvent(
        tenant_id=tenant_id,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        prev_digest=prev_digest,
        digest=digest,
    )
    session.add(event)
    return event
