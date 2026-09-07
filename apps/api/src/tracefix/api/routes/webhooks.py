from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from tracefix.api.deps import AppContext, get_ctx
from tracefix.domain.reasons import ReasonCode
from tracefix.domain.states import RepairRunState
from tracefix.github.schemas import WorkflowRunEvent
from tracefix.github.signature import verify_webhook_signature
from tracefix.policy.admission import AdmissionContext, admit_event
from tracefix.policy.schema import RepositoryPolicy
from tracefix.storage.models import OutboxEvent, RepairRun, Repository, RepositoryPolicyRow, WebhookDelivery

router = APIRouter()


@router.post("/webhooks/github")
async def github_webhook(request: Request) -> dict:
    ctx: AppContext = get_ctx(request)
    body = await request.body()
    if len(body) > 1_000_000:
        raise HTTPException(status_code=413, detail="payload too large")
    signature = request.headers.get("x-hub-signature-256")
    ok = verify_webhook_signature(secret=ctx.settings.github_webhook_secret, body=body, header=signature)
    delivery_id = request.headers.get("x-github-delivery") or str(uuid4())
    event_type = request.headers.get("x-github-event", "")
    digest = hashlib.sha256(body).hexdigest()
    async with ctx.sessions() as session:
        existing = (
            await session.execute(select(WebhookDelivery).where(WebhookDelivery.delivery_id == delivery_id))
        ).scalar_one_or_none()
        if existing:
            return {"accepted": True, "duplicate_delivery": True}
        row = WebhookDelivery(
            delivery_id=delivery_id,
            event_type=event_type,
            payload_digest=digest,
            signature_ok=ok,
            status="received" if ok else "rejected",
        )
        session.add(row)
        if not ok:
            await session.commit()
            raise HTTPException(status_code=401, detail={"code": "SIGNATURE_INVALID", "message": "bad signature"})
        if event_type != "workflow_run":
            await session.commit()
            return {"accepted": True, "ignored": True, "reason": "unsupported event"}
        payload = json.loads(body)
        event = WorkflowRunEvent.model_validate(payload)
        if event.action not in {"completed", "requested"}:
            await session.commit()
            return {"accepted": True, "ignored": True}
        repo = (
            await session.execute(
                select(Repository).where(Repository.github_repo_id == event.repository.id)
            )
        ).scalar_one_or_none()
        if repo is None:
            await session.commit()
            return {"accepted": True, "ignored": True, "reason": "unknown repository"}
        policy_row = (
            await session.execute(
                select(RepositoryPolicyRow)
                .where(
                    RepositoryPolicyRow.tenant_id == repo.tenant_id,
                    RepositoryPolicyRow.repository_id == repo.id,
                )
                .order_by(RepositoryPolicyRow.version.desc())
            )
        ).scalars().first()
        policy = RepositoryPolicy.model_validate(policy_row.document) if policy_row else RepositoryPolicy()
        wr = event.workflow_run
        admission = admit_event(
            policy,
            AdmissionContext(
                event_type=wr.event,
                is_fork=event.repository.fork,
                workflow_id=wr.workflow_id,
                conclusion=wr.conclusion,
                head_sha=wr.head_sha,
                execution_sha=wr.head_sha,
                checkout_trusted=True,
                language_profile_ok=True,
                bot_generated=wr.head_branch.startswith("tracefix/") if wr.head_branch else False,
                installation_selected=repo.selected,
                tenant_suspended=False,
                emergency_stop=False,
            ),
        )
        if not admission.admitted:
            await session.commit()
            return {"accepted": True, "ignored": True, "reason": admission.reason.value}
        logical = (
            f"{event.installation.id if event.installation else 0}:{event.repository.id}:"
            f"{wr.id}:{wr.run_attempt}:{policy_row.version if policy_row else 1}:{wr.head_sha}"
        )
        dup = (
            await session.execute(
                select(RepairRun).where(RepairRun.tenant_id == repo.tenant_id, RepairRun.logical_key == logical)
            )
        ).scalar_one_or_none()
        if dup:
            await session.commit()
            return {"accepted": True, "duplicate_logical": True, "run_id": str(dup.id)}
        run = RepairRun(
            tenant_id=repo.tenant_id,
            repository_id=repo.id,
            github_run_id=wr.id,
            github_attempt=wr.run_attempt,
            installation_github_id=event.installation.id if event.installation else 0,
            source_sha=wr.head_sha,
            base_sha=wr.head_sha,
            execution_sha=wr.head_sha,
            state=RepairRunState.RECEIVED.value,
            reason_code=ReasonCode.ADMITTED.value,
            policy_version=policy_row.version if policy_row else 1,
            workflow_id=f"repair-{uuid4()}",
            logical_key=logical,
            simulated=True,
        )
        session.add(run)
        await session.flush()
        session.add(
            OutboxEvent(
                tenant_id=repo.tenant_id,
                topic="repair.start",
                payload={"run_id": str(run.id)},
                workflow_id=run.workflow_id,
            )
        )
        await session.commit()
        return {"accepted": True, "run_id": str(run.id)}
