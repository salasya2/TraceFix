from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

PENDING_TTL_SECONDS = 600


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


@dataclass
class OIDCStart:
    authorization_url: str
    state: str
    nonce: str
    code_verifier: str


def _authorize_url(issuer: str) -> str:
    base = issuer.rstrip("/")
    if base.endswith("/auth"):
        return base
    if "/protocol/openid-connect" in base:
        return base + "/auth"
    return base + "/authorize"


def start_authorization_code(
    *,
    issuer: str,
    client_id: str,
    redirect_uri: str,
    audience: str,
    extra_scopes: str = "openid email profile",
) -> OIDCStart:
    if not issuer or not client_id:
        raise ValueError("OIDC issuer and client_id are required")
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    verifier, challenge = pkce_pair()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": extra_scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "audience": audience,
        }
    )
    return OIDCStart(
        authorization_url=f"{_authorize_url(issuer)}?{query}",
        state=state,
        nonce=nonce,
        code_verifier=verifier,
    )


def validate_id_token_claims(
    claims: dict,
    *,
    issuer: str,
    audience: str,
    nonce: str,
) -> dict:
    if claims.get("iss") != issuer and not str(claims.get("iss", "")).startswith(issuer.rstrip("/")):
        raise PermissionError("issuer mismatch")
    aud = claims.get("aud")
    if isinstance(aud, list):
        if audience not in aud:
            raise PermissionError("audience mismatch")
    elif aud != audience:
        raise PermissionError("audience mismatch")
    if claims.get("nonce") != nonce:
        raise PermissionError("nonce mismatch")
    now = int(time.time())
    exp = claims.get("exp")
    if exp is not None and int(exp) <= now:
        raise PermissionError("token expired")
    nbf = claims.get("nbf")
    if nbf is not None and int(nbf) > now + 60:
        raise PermissionError("token not yet valid")
    if not claims.get("email") and not claims.get("sub"):
        raise PermissionError("missing subject")
    return claims


def verify_signed_id_token(
    id_token: str,
    *,
    jwks: dict[str, Any],
    issuer: str,
    audience: str,
    nonce: str,
) -> dict:
    from authlib.jose import JsonWebKey, jwt

    key_set = JsonWebKey.import_key_set(jwks)
    claims = jwt.decode(id_token, key_set)
    try:
        claims.validate()
    except Exception as exc:
        raise PermissionError(f"id_token failed validation: {exc}") from exc
    return validate_id_token_claims(dict(claims), issuer=issuer, audience=audience, nonce=nonce)


async def fetch_openid_configuration(issuer: str) -> dict[str, Any]:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def complete_authorization_code(
    *,
    issuer: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    audience: str,
    code: str,
    code_verifier: str,
    nonce: str,
    http: httpx.AsyncClient | None = None,
) -> dict:
    """Exchange an authorization code and verify the ID token signature."""
    owns = http is None
    client = http or httpx.AsyncClient(timeout=20)
    try:
        try:
            config = await fetch_openid_configuration(issuer)
        except Exception:
            config = {}
        token_url = config.get("token_endpoint") or (issuer.rstrip("/") + "/token")
        jwks_url = config.get("jwks_uri") or (issuer.rstrip("/") + "/protocol/openid-connect/certs")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier,
        }
        if client_secret:
            data["client_secret"] = client_secret
        token_response = await client.post(token_url, data=data)
        token_response.raise_for_status()
        payload = token_response.json()
        id_token = payload.get("id_token")
        if not id_token:
            raise PermissionError("token response missing id_token")
        jwks_response = await client.get(jwks_url)
        jwks_response.raise_for_status()
        return verify_signed_id_token(
            id_token,
            jwks=jwks_response.json(),
            issuer=issuer,
            audience=audience,
            nonce=nonce,
        )
    finally:
        if owns:
            await client.aclose()
