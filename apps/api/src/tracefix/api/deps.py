from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tracefix.domain.roles import ADMIN_ROLES, MAINTAINER_ROLES, Role
from tracefix.orchestrator.runner import InvestigationRuntime

from tracefix.api.auth import COOKIE, Principal, read_session
from tracefix.settings import Settings


@dataclass
class AppContext:
    settings: Settings
    sessions: async_sessionmaker[AsyncSession]
    runtime: InvestigationRuntime
    github: Any
    seed_principals: dict[str, Principal]
    oidc_pending: dict[str, dict[str, Any]] = field(default_factory=dict)


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def _session_or_none(secret: str, token: str) -> Principal | None:
    try:
        return read_session(secret, token)
    except PermissionError:
        return None


def get_principal(request: Request, ctx: Annotated[AppContext, Depends(get_ctx)]) -> Principal:
    token = request.cookies.get(COOKIE)
    if token:
        principal = _session_or_none(ctx.settings.secret_key, token)
        if principal:
            return principal
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "invalid session"})
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        raw = header.removeprefix("Bearer ").strip()
        principal = _session_or_none(ctx.settings.secret_key, raw)
        if principal:
            return principal
        if ctx.settings.dev_identities_allowed:
            seeded = ctx.seed_principals.get(raw)
            if seeded:
                return seeded
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "login required"})
    if ctx.settings.dev_identities_allowed:
        principal = ctx.seed_principals.get(ctx.settings.dev_user_email)
        if principal:
            return principal
    raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "login required"})


async def get_session(request: Request, ctx: Annotated[AppContext, Depends(get_ctx)]):
    async with ctx.sessions() as session:
        principal: Principal | None = None
        try:
            principal = get_principal(request, ctx)
        except HTTPException:
            principal = None
        backend = ctx.settings.database_url.split(":", 1)[0]
        if principal is not None and "postgresql" in backend:
            await session.execute(
                text("SELECT set_config('tracefix.tenant_id', :tid, true)"),
                {"tid": str(principal.tenant_id)},
            )
        yield session


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
