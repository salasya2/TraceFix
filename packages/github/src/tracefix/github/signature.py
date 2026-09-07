from __future__ import annotations

import hashlib
import hmac


def verify_webhook_signature(*, secret: str | bytes, body: bytes, header: str | None) -> bool:
    """Verify X-Hub-Signature-256 against the original body bytes.

    Comparison is constant-time. Parsing must not happen before this check
    when the result is used to admit work.
    """
    if not header or not header.startswith("sha256="):
        return False
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    digest = hmac.new(key, body, hashlib.sha256).hexdigest()
    expected = "sha256=" + digest
    return hmac.compare_digest(expected, header)


def sign_body(*, secret: str | bytes, body: bytes) -> str:
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    return "sha256=" + hmac.new(key, body, hashlib.sha256).hexdigest()
