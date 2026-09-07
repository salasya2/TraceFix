from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from tracefix.domain.roles import Role


@dataclass
class Principal:
    user_id: UUID
    tenant_id: UUID
    email: str
    role: Role
    subject: str


def serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="tracefix-session")


def issue_session(secret: str, principal: Principal) -> str:
    return serializer(secret).dumps(
        {
            "user_id": str(principal.user_id),
            "tenant_id": str(principal.tenant_id),
            "email": principal.email,
            "role": principal.role.value,
            "subject": principal.subject,
        }
    )


def read_session(secret: str, token: str, max_age: int = 12 * 3600) -> Principal:
    try:
        data = serializer(secret).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired) as exc:
        raise PermissionError("invalid session") from exc
    return Principal(
        user_id=UUID(data["user_id"]),
        tenant_id=UUID(data["tenant_id"]),
        email=data["email"],
        role=Role(data["role"]),
        subject=data["subject"],
    )


def csrf_token(secret: str, session_token: str) -> str:
    return serializer(secret + "-csrf").dumps({"s": session_token[-12:]})


COOKIE = "tracefix_session"
CSRF_COOKIE = "tracefix_csrf"
