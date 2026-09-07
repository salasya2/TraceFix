from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    retryable: bool = False


class RepairRunOut(BaseModel):
    id: UUID
    state: str
    reason_code: str | None
    reason_detail: str | None
    source_sha: str
    base_sha: str
    execution_sha: str
    simulated: bool
    cost_reserved_usd: float
    cost_actual_usd: float
    diagnosis: dict[str, Any] | None
    limitations: list[str] | None
    github_run_id: int
    github_attempt: int
    created_at: datetime | None = None


class CandidateOut(BaseModel):
    id: UUID
    iteration: int
    patch_digest: str
    verified: bool
    badge: str
    changed_files: list[str]
    validation_errors: list[str]
    model: str


class EventOut(BaseModel):
    state: str
    actor: str
    reason: str | None
    detail: str | None
    at: datetime | None = None
