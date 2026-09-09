from __future__ import annotations

from pathlib import Path

from tracefix._paths import ROOT
from tracefix.agent.fixture_provider import FixtureProvider
from tracefix.agent.providers import AnthropicProvider, SpaceXAIProvider
from tracefix.api.app import create_app
from tracefix.api.deps import AppContext
from tracefix.api.seed import principals, seed_world
from tracefix.executor.adapters.docker import DockerAdapter
from tracefix.executor.adapters.gvisor import GVisorAdapter
from tracefix.executor.adapters.process import ProcessAdapter
from tracefix.executor.broker import ExecutionBroker
from tracefix.github.fixture import FixtureGitHub
from tracefix.github.rest import GitHubREST
from tracefix.orchestrator.runner import InvestigationRuntime
from tracefix.settings import Settings, load_settings, validate_startup
from tracefix.storage.artifacts import ArtifactStore
from tracefix.storage.engine import create_engine_from_url, create_session_factory, init_schema


def select_executor(settings: Settings):
    if settings.executor == "gvisor":
        return GVisorAdapter()
    if settings.executor == "docker":
        return DockerAdapter()
    return ProcessAdapter()


def select_github(settings: Settings):
    if settings.github_token:
        return GitHubREST(settings.github_token, api_url=settings.github_api_url, api_version=settings.github_api_version)
    return FixtureGitHub()


def select_provider_factory(settings: Settings):
    def factory(snapshot: Path, traceback: str):
        name = settings.model_provider
        if name == "fixture":
            return FixtureProvider(snapshot, traceback)
        if name == "anthropic":
            if not settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is required for the anthropic provider")
            return AnthropicProvider(settings.anthropic_api_key)
        if name in {"spacexai", "xai"}:
            if not settings.xai_api_key:
                raise RuntimeError("XAI_API_KEY is required for the spacexai provider")
            return SpaceXAIProvider(settings.xai_api_key, settings.model_base_url)
        raise RuntimeError(f"unknown TRACEFIX_MODEL_PROVIDER={name}")

    return factory


async def build_app_context(settings: Settings | None = None, *, seed: bool = False) -> AppContext:
    settings = settings or load_settings()
    validate_startup(settings)
    engine = create_engine_from_url(settings.database_url)
    await init_schema(engine)
    sessions = create_session_factory(engine)
    artifacts = ArtifactStore(Path(settings.artifact_dir))
    github = select_github(settings)
    runtime = InvestigationRuntime(
        sessions=sessions,
        artifacts=artifacts,
        broker=ExecutionBroker(select_executor(settings)),
        work_root=ROOT / ".data" / "work",
        provider_factory=select_provider_factory(settings),
        model_id=settings.model_id,
    )
    seed_principals = {}
    if seed or (settings.dev_identities_allowed and (settings.seed_demo_data or settings.profile == "embedded")):
        seed_principals = principals()
        if isinstance(github, FixtureGitHub):
            await seed_world(sessions, github, ROOT / "evals" / "tasks" / "tf001-off-by-one")
    return AppContext(
        settings=settings,
        sessions=sessions,
        runtime=runtime,
        github=github,
        seed_principals=seed_principals,
    )


async def serve_app(settings: Settings | None = None):
    import uvicorn

    ctx = await build_app_context(settings)
    app = create_app(ctx, start_dispatcher=True)
    config = uvicorn.Config(
        app,
        host=ctx.settings.api_host,
        port=ctx.settings.api_port,
        log_level=ctx.settings.log_level.lower(),
    )
    await uvicorn.Server(config).serve()
    return 0
