from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class PolicyLimits(BaseModel):
    candidates: int = 3
    changed_files: int = 5
    changed_lines: int = 250  # additions + deletions
    investigation_seconds: int = 900
    sandbox_seconds: int = 300
    sandbox_vcpu: int = 2
    sandbox_memory_mib: int = 4096
    sandbox_pids: int = 256
    sandbox_disk_mib: int = 2048
    max_source_files: int = 20000
    max_expanded_source_mib: int = 200
    max_expanded_logs_mib: int = 50
    model_input_tokens_total: int = 60000
    model_output_tokens_total: int = 10000
    reserved_model_cost_usd: float = 2.00
    queue_expiry_seconds: int = 3600

    @field_validator(
        "candidates",
        "changed_files",
        "changed_lines",
        "investigation_seconds",
        "sandbox_seconds",
        mode="after",
    )
    @classmethod
    def positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("limit must be >= 1")
        return value


class PublicationPolicy(BaseModel):
    draft_only: bool = True
    approval_ttl_seconds: int = 1800
    require_workflow_safety_review: bool = True
    require_separate_approver: bool = False


class RepositoryPolicy(BaseModel):
    schema_version: int = 1
    mode: Literal["approval_required", "report_only", "disabled"] = "approval_required"
    eligible_events: list[str] = Field(default_factory=lambda: ["push", "pull_request"])
    allow_forks: bool = False
    execution_profile: str = "python312-pytest-v1"
    workflow_ids: list[int] = Field(default_factory=list)
    source_paths: list[str] = Field(default_factory=lambda: ["src/"])
    protected_paths: list[str] = Field(
        default_factory=lambda: [
            ".github/",
            "tests/",
            "conftest.py",
            "**/conftest.py",
            "pyproject.toml",
            "pytest.ini",
            "uv.lock",
            "requirements*.txt",
            "deploy/",
            "infra/",
        ]
    )
    limits: PolicyLimits = Field(default_factory=PolicyLimits)
    publication: PublicationPolicy = Field(default_factory=PublicationPolicy)

    def dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


DEFAULT_POLICY = RepositoryPolicy()

PLATFORM_MAX_LIMITS = PolicyLimits(
    candidates=5,
    changed_files=10,
    changed_lines=500,
    investigation_seconds=1800,
    sandbox_seconds=600,
    sandbox_vcpu=4,
    sandbox_memory_mib=8192,
    sandbox_pids=512,
    sandbox_disk_mib=4096,
    max_source_files=40000,
    max_expanded_source_mib=400,
    max_expanded_logs_mib=100,
    model_input_tokens_total=120000,
    model_output_tokens_total=20000,
    reserved_model_cost_usd=10.00,
    queue_expiry_seconds=7200,
)


def clamp_to_platform(policy: RepositoryPolicy) -> RepositoryPolicy:
    data = policy.limits.model_dump()
    ceiling = PLATFORM_MAX_LIMITS.model_dump()
    for key, cap in ceiling.items():
        if isinstance(cap, (int, float)) and data[key] > cap:
            data[key] = cap
    return policy.model_copy(update={"limits": PolicyLimits(**data)})
