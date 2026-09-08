from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tracefix import __version__
from tracefix.api.deps import AppContext
from tracefix.api.errors import install_error_handlers
from tracefix.api.routes import auth_routes, candidates, misc, ops, repair_runs, repos, webhooks


def create_app(ctx: AppContext) -> FastAPI:
    app = FastAPI(
        title="TraceFix API",
        version=__version__,
        description="Investigate failed GitHub Actions runs and independently verify proposed patches.",
    )
    app.state.ctx = ctx
    origins = [ctx.settings.web_origin, ctx.settings.public_url, "http://127.0.0.1:5173", "http://localhost:5173"]
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
        return {"ok": True, "version": __version__, "profile": ctx.settings.profile}

    @app.get("/openapi-version")
    async def pinned() -> dict:
        return {"github_api": ctx.settings.github_api_version, "prompt": ctx.settings.prompt_version}

    return app
