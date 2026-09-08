from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from tracefix.api.auth import COOKIE, CSRF_COOKIE, csrf_token, issue_session
from tracefix.api.deps import AppContext, Viewer, get_ctx
from tracefix.api.oidc import start_authorization_code, validate_id_token_claims

router = APIRouter()


class DevLogin(BaseModel):
    email: str


@router.post("/v1/auth/login")
async def dev_login(body: DevLogin, request: Request, response: Response) -> dict:
    ctx: AppContext = get_ctx(request)
    principal = ctx.seed_principals.get(body.email)
    if principal is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "unknown user"})
    token = issue_session(ctx.settings.secret_key, principal)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=ctx.settings.is_production)
    response.set_cookie(CSRF_COOKIE, csrf_token(ctx.settings.secret_key, token), samesite="lax")
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
async def oidc_start(request: Request) -> dict:
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
    return {
        "authorization_url": started.authorization_url,
        "state": started.state,
        "nonce": started.nonce,
        "code_verifier": started.code_verifier,
    }


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
