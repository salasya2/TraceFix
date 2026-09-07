from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracefix.api.deps import AppContext, Maintainer, Viewer, get_ctx, get_session
from tracefix.domain.states import RepairRunState
from tracefix.policy.schema import RepositoryPolicy
from tracefix.publisher.service import PublishRequest, Publisher
from tracefix.storage.audit import record_audit
from tracefix.storage.models import (
    Approval,
    Artifact,
    Candidate,
    Publication,
    RepairRun,
    Repository,
    RepositoryPolicyRow,
    VerificationRecord,
)

router = APIRouter()


class ApproveBody(BaseModel):
    patch_digest: str


@router.get("/v1/candidates/{candidate_id}")
async def get_candidate(
    candidate_id: UUID,
    principal: Viewer,
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    cand = await session.get(Candidate, candidate_id)
    if cand is None or cand.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})
    patch = ""
    if cand.artifact_id:
        art = await session.get(Artifact, cand.artifact_id)
        if art and art.tenant_id == principal.tenant_id:
            patch = ctx.runtime.artifacts.get(art.storage_key).decode("utf-8", "replace")
    record = (
        await session.execute(
            select(VerificationRecord).where(
                VerificationRecord.candidate_id == cand.id, VerificationRecord.tenant_id == principal.tenant_id
            )
        )
    ).scalar_one_or_none()
    return {
        "id": str(cand.id),
        "iteration": cand.iteration,
        "patch_digest": cand.patch_digest,
        "verified": cand.verified,
        "badge": cand.badge,
        "changed_files": cand.changed_files,
        "validation_errors": cand.validation_errors,
        "patch": patch,
        "verification": record.attestation if record else None,
        "limitations": record.limitations if record else [],
    }


@router.post("/v1/candidates/{candidate_id}/approve")
async def approve_candidate(
    candidate_id: UUID,
    body: ApproveBody,
    principal: Maintainer,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    cand = await session.get(Candidate, candidate_id)
    if cand is None or cand.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})
    if not cand.verified:
        raise HTTPException(status_code=400, detail={"code": "POLICY_DENIED", "message": "candidate is not verified"})
    if body.patch_digest != cand.patch_digest:
        raise HTTPException(
            status_code=400, detail={"code": "APPROVAL_DIGEST_MISMATCH", "message": "digest mismatch"}
        )
    run = await session.get(RepairRun, cand.run_id)
    record = (
        await session.execute(
            select(VerificationRecord).where(VerificationRecord.candidate_id == cand.id)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=400, detail={"code": "POLICY_DENIED", "message": "missing evidence"})
    approval = Approval(
        tenant_id=principal.tenant_id,
        candidate_id=cand.id,
        approver_id=principal.user_id,
        patch_digest=cand.patch_digest,
        source_sha=run.source_sha,
        base_sha=run.base_sha,
        policy_version=run.policy_version,
        evidence_id=record.id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=1800),
    )
    session.add(approval)
    await record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor=principal.email,
        action="approve",
        target_type="candidate",
        target_id=str(cand.id),
        payload={"digest": cand.patch_digest},
    )
    await session.commit()
    return {"id": str(approval.id), "expires_at": approval.expires_at.isoformat()}


@router.post("/v1/candidates/{candidate_id}/publish")
async def publish_candidate(
    candidate_id: UUID,
    principal: Maintainer,
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    cand = await session.get(Candidate, candidate_id)
    if cand is None or cand.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})
    run = await session.get(RepairRun, cand.run_id)
    repo = await session.get(Repository, run.repository_id)
    approval = (
        await session.execute(
            select(Approval)
            .where(Approval.candidate_id == cand.id, Approval.tenant_id == principal.tenant_id)
            .order_by(Approval.expires_at.desc())
        )
    ).scalars().first()
    record = (
        await session.execute(select(VerificationRecord).where(VerificationRecord.candidate_id == cand.id))
    ).scalar_one_or_none()
    policy_row = (
        await session.execute(
            select(RepositoryPolicyRow)
            .where(RepositoryPolicyRow.repository_id == repo.id)
            .order_by(RepositoryPolicyRow.version.desc())
        )
    ).scalars().first()
    policy = RepositoryPolicy.model_validate(policy_row.document) if policy_row else RepositoryPolicy()
    art = await session.get(Artifact, cand.artifact_id) if cand.artifact_id else None
    patch = ctx.runtime.artifacts.get(art.storage_key).decode() if art else ""
    owner, name = repo.full_name.split("/", 1)
    publisher = Publisher(ctx.github)
    result = await publisher.publish(
        policy,
        PublishRequest(
            tenant_id=principal.tenant_id,
            repository_id=repo.id,
            candidate_id=cand.id,
            run_id=run.id,
            github_run_id=run.github_run_id,
            github_attempt=run.github_attempt,
            owner=owner,
            repo=name,
            patch=patch,
            patch_digest=cand.patch_digest,
            source_sha=run.source_sha,
            base_sha=run.base_sha,
            policy_version=run.policy_version,
            evidence_id=record.id if record else cand.id,
            diagnosis_markdown=(run.diagnosis or {}).get("hypothesis", ""),
            verification_markdown=f"badge={cand.badge}",
            safety_ok=repo.publication_mode == "draft_pr",
            safety_fingerprint=repo.safety_fingerprint,
            approved_fingerprint=repo.safety_fingerprint,
            refs_unchanged=True,
            installation_active=True,
            approved=approval is not None,
            approval_expires_at=approval.expires_at if approval else None,
            approved_digest=approval.patch_digest if approval else None,
            approved_source_sha=approval.source_sha if approval else None,
            approved_base_sha=approval.base_sha if approval else None,
            approved_policy_version=approval.policy_version if approval else None,
        ),
    )
    if result.mode == "blocked":
        raise HTTPException(
            status_code=400,
            detail={"code": result.reason.value, "message": result.detail, "retryable": False},
        )
    existing_pub = (
        await session.execute(select(Publication).where(Publication.lock_key == result.lock_key))
    ).scalar_one_or_none()
    if existing_pub:
        return {
            "mode": existing_pub.mode,
            "pr_url": existing_pub.pr_url,
            "pr_number": existing_pub.pr_number,
            "branch": existing_pub.branch,
            "operation_id": existing_pub.operation_id,
        }
    pub = Publication(
        tenant_id=principal.tenant_id,
        candidate_id=cand.id,
        approval_id=approval.id if approval else cand.id,
        operation_id=result.operation_id,
        lock_key=result.lock_key,
        branch=result.branch,
        pr_number=result.pr_number,
        pr_url=result.pr_url,
        mode=result.mode,
        status="completed",
        candidate_digest=cand.patch_digest,
    )
    session.add(pub)
    run.state = (
        RepairRunState.PR_OPENED.value
        if result.mode == "draft_pr"
        else RepairRunState.PATCH_DOWNLOAD_READY.value
    )
    await record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor=principal.email,
        action="publish",
        target_type="candidate",
        target_id=str(cand.id),
        payload={"mode": result.mode, "pr": result.pr_url},
    )
    await session.commit()
    return {
        "mode": result.mode,
        "pr_url": result.pr_url,
        "pr_number": result.pr_number,
        "branch": result.branch,
        "operation_id": result.operation_id,
    }
