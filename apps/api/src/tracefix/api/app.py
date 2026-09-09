from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tracefix import __version__
from tracefix.api.deps import AppContext
from tracefix.api.errors import install_error_handlers
from tracefix.api.routes import auth_routes, candidates, misc, ops, repair_runs, repos, webhooks


def create_app(ctx: AppContext | None = None, *, start_dispatcher: bool = False) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if getattr(app.state, "ctx", None) is None:
            from tracefix.factory import build_app_context

            app.state.ctx = await build_app_context()
        current: AppContext = app.state.ctx
        task = None
        if start_dispatcher or ctx is None:
            from tracefix.orchestrator.outbox import run_dispatcher_loop

            from tracefix._paths import ROOT

            fixture_root = None
            if current.settings.model_provider == "fixture":
                fixture_root = ROOT / "evals" / "tasks" / "tf001-off-by-one"
            task = asyncio.create_task(
                run_dispatcher_loop(current.sessions, current.runtime, current.github, fixture_root=fixture_root)
            )
        try:
            yield
        finally:
            if task is not None:
                task.cancel()

    app = FastAPI(
        title="TraceFix API",
        version=__version__,
        description="Investigate failed GitHub Actions runs and independently verify proposed patches.",
        lifespan=lifespan,
    )
    if ctx is not None:
        app.state.ctx = ctx
    origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
    if ctx is not None:
        origins.extend([ctx.settings.web_origin, ctx.settings.public_url])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(webhooks.router)
    app.include_router(auth_routes.router)
    app.include_router(repos.router)
    app.include_router(repair_runs.router)
    app.include_router(candidates.router)
    app.include_router(misc.router)
    app.include_router(ops.router)

    @app.get("/health")
    async def health() -> dict:
        current = app.state.ctx
        return {"ok": True, "version": __version__, "profile": current.settings.profile}

    @app.get("/openapi-version")
    async def pinned() -> dict:
        current = app.state.ctx
        return {"github_api": current.settings.github_api_version, "prompt": current.settings.prompt_version}

    return app
