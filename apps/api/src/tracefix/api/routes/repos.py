from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tracefix.api.deps import Admin, Viewer, get_session
from tracefix.policy.schema import RepositoryPolicy, clamp_to_platform
from tracefix.storage.audit import record_audit
from tracefix.storage.models import Repository, RepositoryPolicyRow

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
