from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from tracefix.domain.reasons import ReasonCode
from tracefix.domain.states import RepairRunState


class EvidenceRef(BaseModel):
    path: str
    revision: str
    start_line: int | None = None
    end_line: int | None = None
    digest: str | None = None


class Diagnosis(BaseModel):
    failure_category: str
    hypothesis: str
    expected_behavior: str
    known_limitations: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    proposed_changed_paths: list[str] = Field(default_factory=list)
    confidence: float | None = None


class LogicalRunKey(BaseModel):
    installation_id: int
    repository_id: int
    workflow_run_id: int
    run_attempt: int
    policy_version: int
    execution_sha: str

    def encode(self) -> str:
        return (
            f"{self.installation_id}:{self.repository_id}:{self.workflow_run_id}:"
            f"{self.run_attempt}:{self.policy_version}:{self.execution_sha}"
        )


class StateChange(BaseModel):
    run_id: UUID
    from_state: RepairRunState
    to_state: RepairRunState
    reason: ReasonCode
    actor: str
    at: datetime
    workflow_id: str | None = None
    policy_version: int | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    detail: str | None = None
