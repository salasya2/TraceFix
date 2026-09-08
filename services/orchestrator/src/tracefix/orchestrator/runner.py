from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tracefix.agent.fixture_provider import FixtureProvider
from tracefix.agent.loop import run_agent
from tracefix.agent.router import Snapshot, ToolRouter
from tracefix.domain.reasons import ReasonCode
from tracefix.domain.states import RepairRunState
from tracefix.domain.transitions import allowed_transition
from tracefix.executor.adapters.process import ProcessAdapter
from tracefix.executor.broker import ExecutionBroker, JobSpec
from tracefix.orchestrator.budget import BudgetBook
from tracefix.policy.schema import RepositoryPolicy
from tracefix.storage.artifacts import ArtifactStore
from tracefix.storage.models import (
    Artifact,
    Candidate,
    Execution,
    ModelCall,
    RepairRun,
    RepairRunEvent,
    UsageLedger,
    VerificationRecord,
)
from tracefix.verification.pipeline import verify_candidate


@dataclass
class InvestigationRuntime:
    sessions: async_sessionmaker[AsyncSession]
    artifacts: ArtifactStore
    broker: ExecutionBroker = field(default_factory=lambda: ExecutionBroker(ProcessAdapter()))
    budget: BudgetBook = field(default_factory=BudgetBook)
    work_root: Path = field(default_factory=lambda: Path(".data/work"))


async def _transition(
    session: AsyncSession,
    run: RepairRun,
    nxt: RepairRunState,
    *,
    actor: str,
    reason: ReasonCode,
    detail: str | None = None,
) -> None:
    current = RepairRunState(run.state)
    if not allowed_transition(current, nxt):
        raise RuntimeError(f"illegal transition {current} -> {nxt}")
    run.state = nxt.value
    run.reason_code = reason.value
    run.reason_detail = detail
    run.updated_at = datetime.now(timezone.utc)
    session.add(
        RepairRunEvent(
            tenant_id=run.tenant_id,
            run_id=run.id,
            state=nxt.value,
            actor=actor,
            reason=reason.value,
            detail=detail,
            workflow_id=run.workflow_id,
            policy_version=run.policy_version,
        )
    )


async def run_investigation(
    runtime: InvestigationRuntime,
    run_id: UUID,
    *,
    snapshot: Path,
    policy: RepositoryPolicy,
    traceback: str,
    provider_name: str = "fixture",
    model: str = "claude-sonnet-5",
) -> RepairRun:
    async with runtime.sessions() as session:
        run = await session.get(RepairRun, run_id)
        if run is None:
            raise KeyError(run_id)
        await _transition(
            session, run, RepairRunState.ADMITTED, actor="orchestrator", reason=ReasonCode.ADMITTED
        )
        await session.commit()

        dest = runtime.work_root / str(run.id) / "snapshot"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(snapshot, dest)
        tree_hash = hashlib.sha256(str(dest).encode()).hexdigest()
        art = runtime.artifacts.put(
            tenant_id=run.tenant_id, kind="snapshot", data=tree_hash.encode(), run_id=run.id
        )
        session.add(art)
        await _transition(
            session,
            run,
            RepairRunState.SNAPSHOTTED,
            actor="orchestrator",
            reason=ReasonCode.ADMITTED,
            detail="source snapshot stored",
        )
        await session.commit()

        await _transition(
            session,
            run,
            RepairRunState.BASELINE_RUNNING,
            actor="executor",
            reason=ReasonCode.ADMITTED,
        )
        spec = JobSpec(
            tenant_id=str(run.tenant_id),
            run_id=str(run.id),
            capability=runtime.broker.issue_capability(str(run.tenant_id), str(run.id), "verify"),
            source_digest=tree_hash,
            image_digest="local-python",
            dependency_bundle_digest="none",
            profile_id=policy.execution_profile,
            stage="verify",
            snapshot=dest,
            timeout_seconds=policy.limits.sandbox_seconds,
        )
        baseline = await runtime.broker.run_tests(spec)
        session.add(
            Execution(
                tenant_id=run.tenant_id,
                run_id=run.id,
                stage="verify",
                status="completed",
                exit_code=baseline.exit_code,
                limits={"timeout": policy.limits.sandbox_seconds},
            )
        )
        if baseline.timed_out:
            await _transition(
                session,
                run,
                RepairRunState.UNREPRODUCIBLE,
                actor="executor",
                reason=ReasonCode.TARGET_NOT_REPRODUCED,
                detail="baseline timed out",
            )
            await session.commit()
            return run
        if not baseline.inventory.failed_ids:
            await _transition(
                session,
                run,
                RepairRunState.UNREPRODUCIBLE,
                actor="executor",
                reason=ReasonCode.TARGET_NOT_REPRODUCED,
                detail="baseline did not fail",
            )
            await session.commit()
            return run
        await _transition(
            session,
            run,
            RepairRunState.REPRODUCED,
            actor="executor",
            reason=ReasonCode.ADMITTED,
            detail=baseline.inventory.signature(),
        )
        await session.commit()

        try:
            lease = runtime.budget.reserve(run.tenant_id, run.id, policy.limits.reserved_model_cost_usd)
        except RuntimeError:
            await _transition(
                session,
                run,
                RepairRunState.BUDGET_EXCEEDED,
                actor="orchestrator",
                reason=ReasonCode.BUDGET_EXCEEDED,
            )
            await session.commit()
            return run
        session.add(
            UsageLedger(
                tenant_id=run.tenant_id,
                run_id=run.id,
                kind="reservation",
                amount_usd=lease.reserved,
            )
        )

        await _transition(
            session, run, RepairRunState.DIAGNOSING, actor="agent", reason=ReasonCode.ADMITTED
        )
        await session.commit()

        snap = Snapshot(
            snapshot_id="current",
            tenant_id=str(run.tenant_id),
            run_id=str(run.id),
            root=dest,
        )
        router = ToolRouter(policy, {"current": snap})
        provider = FixtureProvider(dest, traceback)
        outcome = await run_agent(
            provider,
            router,
            tenant_id=str(run.tenant_id),
            run_id=str(run.id),
            traceback=traceback,
            snapshot_id="current",
            execution_sha=run.execution_sha,
            tests=",".join(sorted(baseline.inventory.failed_ids)),
            model=model,
        )
        session.add(
            ModelCall(
                tenant_id=run.tenant_id,
                run_id=run.id,
                provider=provider.name,
                model=model,
                prompt_version=outcome.prompt_version,
                input_tokens=outcome.input_tokens,
                output_tokens=outcome.output_tokens,
                cost_usd=0.0 if outcome.simulated else 0.0,
            )
        )
        runtime.budget.settle(lease.id, 0.0 if outcome.simulated else min(lease.reserved, 0.05))
        run.simulated = outcome.simulated
        if outcome.diagnosis:
            run.diagnosis = outcome.diagnosis.model_dump()
        if not outcome.patch:
            await _transition(
                session,
                run,
                RepairRunState.NO_VALID_PATCH,
                actor="agent",
                reason=ReasonCode.NO_VALID_PATCH,
            )
            await session.commit()
            return run

        candidate = Candidate(
            tenant_id=run.tenant_id,
            run_id=run.id,
            iteration=1,
            patch_digest=hashlib.sha256(outcome.patch.encode()).hexdigest(),
            changed_files=[],
            model=model,
            prompt_version=outcome.prompt_version,
            validation_status="proposed",
        )
        session.add(candidate)
        await session.flush()
        patch_art = runtime.artifacts.put(
            tenant_id=run.tenant_id,
            kind="patch",
            data=outcome.patch.encode(),
            access_class="source",
            run_id=run.id,
        )
        session.add(patch_art)
        candidate.artifact_id = patch_art.id
        await _transition(
            session, run, RepairRunState.PATCH_PROPOSED, actor="agent", reason=ReasonCode.ADMITTED
        )
        await _transition(
            session, run, RepairRunState.VERIFYING, actor="verifier", reason=ReasonCode.ADMITTED
        )
        await session.commit()

        verify_root = runtime.work_root / str(run.id) / "verify"
        result = verify_candidate(
            dest,
            outcome.patch,
            policy,
            work_root=verify_root,
            timeout_seconds=policy.limits.sandbox_seconds,
        )
        candidate.validation_status = "accepted" if result.verified else "rejected"
        candidate.validation_errors = result.errors
        candidate.verified = result.verified
        candidate.badge = result.badge
        candidate.changed_files = result.patch_decision.changed_files if result.patch_decision else []
        candidate.changed_lines = result.patch_decision.changed_lines if result.patch_decision else 0
        session.add(
            VerificationRecord(
                tenant_id=run.tenant_id,
                run_id=run.id,
                candidate_id=candidate.id,
                baseline_digest=result.baseline.junit_digest if result.baseline else None,
                candidate_digest=result.patch_digest,
                target_passed=result.target_passed,
                badge=result.badge,
                attestation={
                    "source_sha": run.source_sha,
                    "execution_sha": run.execution_sha,
                    "base_sha": run.base_sha,
                    "patch_digest": result.patch_digest,
                    "tree_digest": result.tree_digest,
                    "profile": policy.execution_profile,
                    "policy_version": run.policy_version,
                    "target_ids": result.target_ids,
                    "errors": result.errors,
                },
                limitations=result.limitations,
            )
        )
        run.limitations = result.limitations
        if result.flaky:
            await _transition(
                session,
                run,
                RepairRunState.FLAKY_SUSPECTED,
                actor="verifier",
                reason=ReasonCode.FLAKY_BASELINE,
            )
        elif not result.verified:
            await _transition(
                session,
                run,
                RepairRunState.NO_VALID_PATCH,
                actor="verifier",
                reason=ReasonCode.VERIFICATION_FAILED,
                detail="; ".join(result.errors),
            )
        else:
            await _transition(
                session,
                run,
                RepairRunState.AWAITING_APPROVAL,
                actor="verifier",
                reason=ReasonCode.VERIFIED,
                detail=result.badge,
            )
        await session.commit()
        await session.refresh(run)
        return run
