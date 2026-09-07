from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set tenant context for this transaction only. Safe with pooled connections."""
    await session.execute(text("SELECT set_config('tracefix.tenant_id', :tid, true)"), {"tid": tenant_id})


async def reset_tenant_context(session: AsyncSession) -> None:
    await session.execute(text("SELECT set_config('tracefix.tenant_id', '', true)"))
