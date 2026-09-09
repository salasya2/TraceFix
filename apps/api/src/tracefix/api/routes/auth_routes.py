from __future__ import annotations

import time
from typing import Annotated
from uuid import NAMESPACE_DNS, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tracefix.domain.roles import Role
from tracefix.storage.models import Membership

from tracefix.api.auth import COOKIE, CSRF_COOKIE, Principal, csrf_token, issue_session
from tracefix.api.deps import AppContext, Viewer, get_ctx, get_session
from tracefix.api.oidc import (
    PENDING_TTL_SECONDS,
    complete_authorization_code,
    start_authorization_code,
    validate_id_token_claims,
)

router = APIRouter()


class DevLogin(BaseModel):
    email: str


def _set_session_cookies(response: Response, ctx: AppContext, principal: Principal) -> None:
    token = issue_session(ctx.settings.secret_key, principal)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=ctx.settings.is_production)
    response.set_cookie(CSRF_COOKIE, csrf_token(ctx.settings.secret_key, token), samesite="lax")


@router.get("/v1/auth/config")
async def auth_config(request: Request) -> dict:
    ctx: AppContext = get_ctx(request)
    return {
        "auth_mode": ctx.settings.auth_mode,
        "dev_login": ctx.settings.dev_identities_allowed,
        "oidc_configured": bool(ctx.settings.oidc_issuer and ctx.settings.oidc_client_id),
    }


@router.post("/v1/auth/login")
async def dev_login(body: DevLogin, request: Request, response: Response) -> dict:
    ctx: AppContext = get_ctx(request)
    if not ctx.settings.dev_identities_allowed:
        raise HTTPException(
            status_code=403,
            detail={"code": "POLICY_DENIED", "message": "development login is disabled"},
        )
    principal = ctx.seed_principals.get(body.email)
    if principal is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "unknown user"})
    _set_session_cookies(response, ctx, principal)
    return {"email": principal.email, "role": principal.role.value, "tenant_id": str(principal.tenant_id)}


@router.get("/v1/auth/me")
async def me(principal: Viewer) -> dict:
    return {
        "email": principal.email,
        "role": principal.role.value,
        "tenant_id": str(principal.tenant_id),
        "user_id": str(principal.user_id),
    }


@router.post("/v1/auth/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return {"ok": True}


@router.get("/v1/auth/oidc/start")
async def oidc_start(request: Request, response: Response) -> dict:
    ctx: AppContext = get_ctx(request)
    try:
        started = start_authorization_code(
            issuer=ctx.settings.oidc_issuer,
            client_id=ctx.settings.oidc_client_id,
            redirect_uri=ctx.settings.public_url.rstrip("/") + "/v1/auth/oidc/callback",
            audience=ctx.settings.oidc_audience,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "UNSUPPORTED_PROFILE", "message": str(exc)}) from exc
    ctx.oidc_pending[started.state] = {
        "nonce": started.nonce,
        "code_verifier": started.code_verifier,
        "created_at": time.time(),
    }
    response.set_cookie("tracefix_oidc_state", started.state, httponly=True, samesite="lax", max_age=PENDING_TTL_SECONDS)
    return {"authorization_url": started.authorization_url, "state": started.state}


class OIDCFinish(BaseModel):
    issuer: str
    audience: str
    nonce: str
    claims: dict


@router.post("/v1/auth/oidc/validate-claims")
async def oidc_validate(body: OIDCFinish) -> dict:
    claims = validate_id_token_claims(
        body.claims, issuer=body.issuer, audience=body.audience, nonce=body.nonce
    )
    return {"email": claims.get("email"), "sub": claims.get("sub")}


async def _principal_from_claims(session: AsyncSession, claims: dict) -> Principal:
    email = str(claims.get("email") or "")
    subject = str(claims.get("sub") or "")
    stmt = select(Membership).where(Membership.status == "active")
    if email and subject:
        stmt = stmt.where((Membership.email == email) | (Membership.subject == subject))
    elif email:
        stmt = stmt.where(Membership.email == email)
    elif subject:
        stmt = stmt.where(Membership.subject == subject)
    else:
        raise HTTPException(status_code=403, detail={"code": "POLICY_DENIED", "message": "missing identity claims"})
    membership = (await session.execute(stmt)).scalars().first()
    if membership is None:
        raise HTTPException(status_code=403, detail={"code": "POLICY_DENIED", "message": "no organization membership"})
    user_id = uuid5(NAMESPACE_DNS, f"{membership.tenant_id}:{membership.email}")
    return Principal(
        user_id=user_id,
        tenant_id=membership.tenant_id,
        email=membership.email,
        role=Role(membership.role),
        subject=membership.subject,
    )


@router.get("/v1/auth/oidc/callback")
async def oidc_callback(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    ctx: AppContext = get_ctx(request)
    if error:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": error})
    if not code or not state:
        raise HTTPException(status_code=400, detail={"code": "UNAUTHENTICATED", "message": "missing code or state"})
    pending = ctx.oidc_pending.get(state)
    cookie_state = request.cookies.get("tracefix_oidc_state")
    if pending is None or (cookie_state and cookie_state != state):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "unknown or expired OIDC state"})
    if time.time() - float(pending.get("created_at", 0)) > PENDING_TTL_SECONDS:
        ctx.oidc_pending.pop(state, None)
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "OIDC state expired"})
    try:
        claims = await complete_authorization_code(
            issuer=ctx.settings.oidc_issuer,
            client_id=ctx.settings.oidc_client_id,
            client_secret=ctx.settings.oidc_client_secret,
            redirect_uri=ctx.settings.public_url.rstrip("/") + "/v1/auth/oidc/callback",
            audience=ctx.settings.oidc_audience,
            code=code,
            code_verifier=pending["code_verifier"],
            nonce=pending["nonce"],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "OIDC exchange failed"}) from exc
    ctx.oidc_pending.pop(state, None)
    principal = await _principal_from_claims(session, claims)
    _set_session_cookies(response, ctx, principal)
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"email": principal.email, "role": principal.role.value, "tenant_id": str(principal.tenant_id)}
    return RedirectResponse(ctx.settings.web_origin.rstrip("/") + "/", status_code=302)
