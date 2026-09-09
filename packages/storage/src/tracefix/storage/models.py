from __future__ import annotations

import uuid
from datetime import datetime, timezone as _tz

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(_tz.utc)


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    oidc_issuer: Mapped[str | None] = mapped_column(String(400), nullable=True)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    subject: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    __table_args__ = (
        UniqueConstraint("tenant_id", "email"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )


class Installation(Base):
    __tablename__ = "installations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    github_installation_id: Mapped[int] = mapped_column(Integer)
    account_login: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="active")
    __table_args__ = (
        UniqueConstraint("tenant_id", "github_installation_id"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )


class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    installation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    github_repo_id: Mapped[int] = mapped_column(Integer)
    full_name: Mapped[str] = mapped_column(String(300))
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    mode: Mapped[str] = mapped_column(String(32), default="approval_required")
    safety_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    publication_mode: Mapped[str] = mapped_column(String(32), default="patch_download")
    __table_args__ = (
        UniqueConstraint("tenant_id", "github_repo_id"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        ForeignKeyConstraint(["tenant_id", "installation_id"], ["installations.tenant_id", "installations.id"]),
    )


class RepositoryPolicyRow(Base):
    __tablename__ = "repository_policies"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict] = mapped_column(JSON)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    __table_args__ = (
        UniqueConstraint("tenant_id", "repository_id", "version"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        ForeignKeyConstraint(["tenant_id", "repository_id"], ["repositories.tenant_id", "repositories.id"]),
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    delivery_id: Mapped[str] = mapped_column(String(80), unique=True)
    event_type: Mapped[str] = mapped_column(String(80))
    payload_digest: Mapped[str] = mapped_column(String(64))
    signature_ok: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(32), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    topic: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    workflow_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RepairRun(Base):
    __tablename__ = "repair_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    github_run_id: Mapped[int] = mapped_column(Integer)
    github_attempt: Mapped[int] = mapped_column(Integer)
    installation_github_id: Mapped[int] = mapped_column(Integer)
    source_sha: Mapped[str] = mapped_column(String(64))
    base_sha: Mapped[str] = mapped_column(String(64))
    execution_sha: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(40), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    workflow_id: Mapped[str] = mapped_column(String(200))
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    logical_key: Mapped[str] = mapped_column(String(300))
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_reserved_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_actual_usd: Mapped[float] = mapped_column(Float, default=0.0)
    diagnosis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    limitations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    __table_args__ = (
        UniqueConstraint("tenant_id", "logical_key"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        ForeignKeyConstraint(["tenant_id", "repository_id"], ["repositories.tenant_id", "repositories.id"]),
    )


class RepairRunEvent(Base):
    __tablename__ = "repair_run_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    state: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "run_id"], ["repair_runs.tenant_id", "repair_runs.id"]),
    )


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    iteration: Mapped[int] = mapped_column(Integer)
    patch_digest: Mapped[str] = mapped_column(String(64))
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    changed_files: Mapped[list] = mapped_column(JSON, default=list)
    changed_lines: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    validation_status: Mapped[str] = mapped_column(String(32), default="pending")
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    badge: Mapped[str] = mapped_column(String(16), default="none")
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "iteration"),
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "run_id"], ["repair_runs.tenant_id", "repair_runs.id"]),
    )


class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    stage: Mapped[str] = mapped_column(String(32))
    image_digest: Mapped[str] = mapped_column(String(128), default="local-python")
    dep_digest: Mapped[str] = mapped_column(String(128), default="none")
    profile_id: Mapped[str] = mapped_column(String(80), default="python312-pytest-v1")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    sandbox_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cleanup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    limits: Mapped[dict] = mapped_column(JSON, default=dict)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VerificationRecord(Base):
    __tablename__ = "verification_records"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    baseline_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_digest: Mapped[str] = mapped_column(String(64))
    target_passed: Mapped[bool] = mapped_column(Boolean)
    badge: Mapped[str] = mapped_column(String(16))
    attestation: Mapped[dict] = mapped_column(JSON)
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    approver_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    patch_digest: Mapped[str] = mapped_column(String(64))
    source_sha: Mapped[str] = mapped_column(String(64))
    base_sha: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[int] = mapped_column(Integer)
    evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safety_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    installation_active: Mapped[bool] = mapped_column(Boolean, default=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Publication(Base):
    __tablename__ = "publications"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    approval_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    operation_id: Mapped[str] = mapped_column(String(200), unique=True)
    lock_key: Mapped[str] = mapped_column(String(300), unique=True)
    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="requested")
    candidate_digest: Mapped[str] = mapped_column(String(64))
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ModelCall(Base):
    __tablename__ = "model_calls"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pricing_version: Mapped[str] = mapped_column(String(40), default="2026-09-07")
    context_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)


class UsageLedger(Base):
    __tablename__ = "usage_ledger"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    amount_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    sandbox_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    storage_key: Mapped[str] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    access_class: Mapped[str] = mapped_column(String(32), default="redacted")
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    prev_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    digest: Mapped[str] = mapped_column(String(64))


class BudgetLease(Base):
    __tablename__ = "budget_leases"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    scope: Mapped[str] = mapped_column(String(80))
    reserved_usd: Mapped[float] = mapped_column(Float)
    settled_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="reserved")
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class PublicationLock(Base):
    __tablename__ = "publication_locks"
    lock_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    publication_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    candidate_digest: Mapped[str] = mapped_column(String(64))
