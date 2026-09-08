from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from tracefix.storage.artifacts import ArtifactStore
from tracefix.storage.engine import create_engine_from_url, create_session_factory, init_schema
from tracefix.storage.models import Artifact
from tracefix.storage.retention import apply_retention


@pytest.mark.asyncio
async def test_expired_artifacts_are_removed(tmp_path: Path):
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    await init_schema(engine)
    sessions = create_session_factory(engine)
    store = ArtifactStore(tmp_path / "art")
    tenant = uuid4()
    art = store.put(tenant_id=tenant, kind="patch", data=b"diff", access_class="source")
    art.retention_until = datetime.now(timezone.utc) - timedelta(days=1)
    async with sessions() as session:
        session.add(art)
        await session.commit()
    async with sessions() as session:
        result = await apply_retention(session, store, now=datetime.now(timezone.utc) + timedelta(days=1))
        await session.commit()
        assert result["artifacts"] >= 1
