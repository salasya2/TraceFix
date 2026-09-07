from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from tracefix.storage.models import Base


def create_engine_from_url(url: str) -> AsyncEngine:
    kwargs: dict = {"echo": False, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        db_path = url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def _fk_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.url.get_backend_name().startswith("postgresql"):
            await conn.run_sync(_apply_rls)


def _apply_rls(sync_conn) -> None:
    tables = [
        "memberships",
        "installations",
        "repositories",
        "repository_policies",
        "repair_runs",
        "repair_run_events",
        "candidates",
        "executions",
        "verification_records",
        "approvals",
        "publications",
        "model_calls",
        "usage_ledger",
        "artifacts",
        "audit_events",
        "budget_leases",
    ]
    for table in tables:
        sync_conn.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        sync_conn.exec_driver_sql(
            f"""
            DROP POLICY IF EXISTS tenant_isolation ON {table};
            CREATE POLICY tenant_isolation ON {table}
              USING (tenant_id = current_setting('tracefix.tenant_id')::uuid)
              WITH CHECK (tenant_id = current_setting('tracefix.tenant_id')::uuid);
            """
        )


@asynccontextmanager
async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
