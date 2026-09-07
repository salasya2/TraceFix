from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tracefix.api.auth import COOKIE, Principal, read_session
from tracefix.domain.roles import ADMIN_ROLES, MAINTAINER_ROLES, Role
from tracefix.github.fixture import FixtureGitHub
from tracefix.orchestrator.runner import InvestigationRuntime
from tracefix.settings import Settings


@dataclass
class AppContext:
    settings: Settings
    sessions: async_sessionmaker[AsyncSession]
    runtime: InvestigationRuntime
    github: FixtureGitHub
    seed_principals: dict[str, Principal]


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


async def get_session(ctx: Annotated[AppContext, Depends(get_ctx)]):
    async with ctx.sessions() as session:
        yield session


def get_principal(request: Request, ctx: Annotated[AppContext, Depends(get_ctx)]) -> Principal:
    token = request.cookies.get(COOKIE)
    if token:
        return read_session(ctx.settings.secret_key, token)
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        email = header.removeprefix("Bearer ").strip()
        principal = ctx.seed_principals.get(email)
        if principal:
            return principal
    if ctx.settings.auth_mode == "dev":
        principal = ctx.seed_principals.get(ctx.settings.dev_user_email)
        if principal:
            return principal
    raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "login required"})


def require_role(*roles: Role):
    allowed = set(roles)

    def _inner(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail={"code": "POLICY_DENIED", "message": "insufficient role"})
        return principal

    return _inner


Maintainer = Annotated[Principal, Depends(require_role(*MAINTAINER_ROLES))]
Admin = Annotated[Principal, Depends(require_role(*ADMIN_ROLES))]
Viewer = Annotated[Principal, Depends(get_principal)]
