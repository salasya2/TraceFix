from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracefix.api.deps import Admin, Maintainer, Viewer, get_session
from tracefix.domain.states import RepairRunState
from tracefix.policy.schema import RepositoryPolicy, clamp_to_platform
from tracefix.storage.audit import record_audit
from tracefix.storage.models import OutboxEvent, RepairRun, Repository, RepositoryPolicyRow

router = APIRouter()


class PolicyUpdate(BaseModel):
    document: dict
    expected_version: int


@router.get("/v1/repositories")
async def list_repos(principal: Viewer, session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    rows = (
        (await session.execute(select(Repository).where(Repository.tenant_id == principal.tenant_id)))
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "full_name": r.full_name,
                "mode": r.mode,
                "selected": r.selected,
                "publication_mode": r.publication_mode,
                "safety_fingerprint": r.safety_fingerprint,
            }
            for r in rows
        ]
    }


@router.put("/v1/repositories/{repo_id}/policy")
async def put_policy(
    repo_id: UUID,
    body: PolicyUpdate,
    principal: Admin,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    repo = await session.get(Repository, repo_id)
    if repo is None or repo.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})
    current = (
        await session.execute(
            select(RepositoryPolicyRow)
            .where(RepositoryPolicyRow.repository_id == repo.id)
            .order_by(RepositoryPolicyRow.version.desc())
        )
    ).scalars().first()
    current_version = current.version if current else 0
    if body.expected_version != current_version:
        raise HTTPException(status_code=409, detail={"code": "VERSION_CONFLICT", "message": "stale policy version"})
    policy = clamp_to_platform(RepositoryPolicy.model_validate(body.document))
    row = RepositoryPolicyRow(
        tenant_id=principal.tenant_id,
        repository_id=repo.id,
        version=current_version + 1,
        document=policy.dump(),
        approver_id=principal.user_id,
    )
    session.add(row)
    repo.mode = policy.mode
    await record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor=principal.email,
        action="policy.update",
        target_type="repository",
        target_id=str(repo.id),
        payload={"version": row.version},
    )
    await session.commit()
    return {"version": row.version, "document": policy.dump()}


class ManualInvestigation(BaseModel):
    github_run_id: int
    github_attempt: int = 1
    source_sha: str
    execution_sha: str
    base_sha: str | None = None


@router.post("/v1/repositories/{repo_id}/repair-runs")
async def manual_repair_run(
    repo_id: UUID,
    body: ManualInvestigation,
    principal: Maintainer,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    repo = await session.get(Repository, repo_id)
    if repo is None or repo.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "not found"})
    policy_row = (
        await session.execute(
            select(RepositoryPolicyRow)
            .where(RepositoryPolicyRow.repository_id == repo.id)
            .order_by(RepositoryPolicyRow.version.desc())
        )
    ).scalars().first()
    version = policy_row.version if policy_row else 1
    logical = (
        f"manual:{repo.github_repo_id}:{body.github_run_id}:{body.github_attempt}:{version}:{body.execution_sha}"
    )
    existing = (
        await session.execute(
            select(RepairRun).where(RepairRun.tenant_id == principal.tenant_id, RepairRun.logical_key == logical)
        )
    ).scalar_one_or_none()
    if existing:
        return {"id": str(existing.id), "duplicate_logical": True}
    run = RepairRun(
        tenant_id=principal.tenant_id,
        repository_id=repo.id,
        github_run_id=body.github_run_id,
        github_attempt=body.github_attempt,
        installation_github_id=0,
        source_sha=body.source_sha,
        base_sha=body.base_sha or body.source_sha,
        execution_sha=body.execution_sha,
        state=RepairRunState.RECEIVED.value,
        policy_version=version,
        workflow_id=f"repair-{uuid4()}",
        logical_key=logical,
        simulated=True,
    )
    session.add(run)
    await session.flush()
    session.add(
        OutboxEvent(
            tenant_id=principal.tenant_id,
            topic="repair.start",
            payload={"run_id": str(run.id)},
            workflow_id=run.workflow_id,
        )
    )
    await session.commit()
    return {"id": str(run.id), "workflow_id": run.workflow_id}
