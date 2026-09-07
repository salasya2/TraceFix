from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
for rel in [
    "packages/domain/src",
    "packages/policy/src",
    "packages/github/src",
    "packages/agent/src",
    "packages/verification/src",
    "packages/storage/src",
    "apps/api/src",
    "services/orchestrator/src",
    "services/executor/src",
    "services/publisher/src",
    "services/credential_broker/src",
    "",
]:
    sys.path.insert(0, str(ROOT / rel) if rel else str(ROOT))

import pytest_asyncio
from tracefix.api.deps import AppContext
from tracefix.api.seed import principals, seed_world
from tracefix.github.fixture import FixtureGitHub
from tracefix.orchestrator.runner import InvestigationRuntime
from tracefix.settings import Settings
from tracefix.storage.artifacts import ArtifactStore
from tracefix.storage.engine import create_engine_from_url, create_session_factory, init_schema

FIXTURE = ROOT / "evals" / "tasks" / "tf001-off-by-one"


@pytest_asyncio.fixture
async def ctx(tmp_path: Path) -> AppContext:
    db = tmp_path / "t.db"
    engine = create_engine_from_url(f"sqlite+aiosqlite:///{db}")
    await init_schema(engine)
    sessions = create_session_factory(engine)
    github = FixtureGitHub()
    await seed_world(sessions, github, FIXTURE)
    settings = Settings()
    runtime = InvestigationRuntime(
        sessions=sessions,
        artifacts=ArtifactStore(tmp_path / "art"),
        work_root=tmp_path / "work",
    )
    return AppContext(
        settings=settings,
        sessions=sessions,
        runtime=runtime,
        github=github,
        seed_principals=principals(),
    )
