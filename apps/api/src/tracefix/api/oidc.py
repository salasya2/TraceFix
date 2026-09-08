from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode


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
    base = issuer.rstrip("/")
    if base.endswith("/auth"):
        authorize = base
    elif "/protocol/openid-connect" in base:
        authorize = base + "/auth"
    else:
        authorize = base + "/authorize"
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
        authorization_url=f"{authorize}?{query}",
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
    if not claims.get("email") and not claims.get("sub"):
        raise PermissionError("missing subject")
    return claims
