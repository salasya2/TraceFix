from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracefix.storage.artifacts import ArtifactStore
from tracefix.storage.models import Artifact, AuditEvent, RepairRun

RAW_DAYS = 7
REPORT_DAYS = 30
AUDIT_DAYS = 90


async def apply_retention(
    session: AsyncSession,
    store: ArtifactStore,
    *,
    now: datetime | None = None,
    raw_days: int = RAW_DAYS,
    report_days: int = REPORT_DAYS,
    audit_days: int = AUDIT_DAYS,
) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    deleted_art = 0
    rows = (await session.execute(select(Artifact))).scalars().all()
    for art in rows:
        expiry = art.retention_until
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        stale = bool(expiry and expiry <= now)
        # Artifacts without explicit expiry use class defaults from "now" only when marked.
        if stale:
            path = store.root / art.storage_key
            if path.exists():
                path.unlink()
            await session.delete(art)
            deleted_art += 1
    deleted_audit = 0
    audit_cutoff = now - timedelta(days=audit_days)
    audits = (await session.execute(select(AuditEvent))).scalars().all()
    for event in audits:
        at = event.at
        if at is None:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if at < audit_cutoff:
            await session.delete(event)
            deleted_audit += 1
    return {"artifacts": deleted_art, "audit_events": deleted_audit}


async def suspend_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    from tracefix.storage.models import Tenant

    tenant = await session.get(Tenant, tenant_id)
    if tenant:
        tenant.status = "suspended"
        tenant.emergency_stop = True
