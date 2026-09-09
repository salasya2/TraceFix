from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tracefix.agent.fixture_provider import FixtureProvider
from tracefix.agent.loop import run_agent
from tracefix.agent.providers import ModelProvider
from tracefix.agent.router import Snapshot, ToolRouter
from tracefix.domain.reasons import ReasonCode
from tracefix.domain.states import RepairRunState, TerminalStates
from tracefix.domain.transitions import allowed_transition
from tracefix.executor.adapters.process import ProcessAdapter
from tracefix.executor.broker import ExecutionBroker, JobSpec
from tracefix.github.snapshot import snapshot_digest
from tracefix.orchestrator.budget import BudgetBook
from tracefix.policy.schema import RepositoryPolicy
from tracefix.storage.artifacts import ArtifactStore
from tracefix.storage.models import (
    Candidate,
    Execution,
    ModelCall,
    RepairRun,
    RepairRunEvent,
    UsageLedger,
    VerificationRecord,
)
from tracefix.verification.pipeline import averify_candidate

try:
    from tracefix.api.metrics import RUNS, VERIFY
except Exception:  # pragma: no cover - metrics are optional for library use
    class _Noop:
        def labels(self, **_kwargs):
            return self

        def inc(self) -> None:
            return None

    RUNS = VERIFY = _Noop()


ProviderFactory = Callable[[Path, str], ModelProvider]


@dataclass
class InvestigationRuntime:
    sessions: async_sessionmaker[AsyncSession]
    artifacts: ArtifactStore
    broker: ExecutionBroker = field(default_factory=lambda: ExecutionBroker(ProcessAdapter()))
    budget: BudgetBook = field(default_factory=BudgetBook)
    work_root: Path = field(default_factory=lambda: Path(".data/work"))
    provider_factory: ProviderFactory | None = None
    model_id: str = "claude-sonnet-5"
    crash_after: str | None = None


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
    if current == nxt:
        return
    if current in TerminalStates:
        return
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
    RUNS.labels(state=nxt.value).inc()


def _maybe_crash(runtime: InvestigationRuntime, stage: str) -> None:
    if runtime.crash_after == stage:
        raise RuntimeError(f"injected crash after {stage}")


async def _cancelled(session: AsyncSession, run: RepairRun, runtime: InvestigationRuntime) -> bool:
    await session.refresh(run)
    if run.state == RepairRunState.CANCELLED.value:
        await runtime.broker.terminate_run(str(run.id))
        return True
    return False


def _job(runtime: InvestigationRuntime, run: RepairRun, snapshot: Path, stage: str, timeout: int) -> JobSpec:
    return JobSpec(
        tenant_id=str(run.tenant_id),
        run_id=str(run.id),
        capability=runtime.broker.issue_capability(str(run.tenant_id), str(run.id), stage),
        source_digest=snapshot_digest(snapshot) if snapshot.exists() else "pending",
        image_digest="local-python",
        dependency_bundle_digest="none",
        profile_id="python312-pytest-v1",
        stage=stage,
        snapshot=snapshot,
        timeout_seconds=timeout,
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
        current = RepairRunState(run.state)
        if current in TerminalStates or current == RepairRunState.AWAITING_APPROVAL:
            return run

        dest = runtime.work_root / str(run.id) / "snapshot"
        dest.parent.mkdir(parents=True, exist_ok=True)

        if current == RepairRunState.RECEIVED:
            await _transition(session, run, RepairRunState.ADMITTED, actor="orchestrator", reason=ReasonCode.ADMITTED)
            await session.commit()
            _maybe_crash(runtime, "admitted")

        if RepairRunState(run.state) in {RepairRunState.ADMITTED, RepairRunState.RECEIVED} or not dest.exists():
            import shutil

            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(snapshot, dest)
            tree_hash = snapshot_digest(dest)
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
            _maybe_crash(runtime, "snapshotted")

        if await _cancelled(session, run, runtime):
            return run

        if RepairRunState(run.state) in {RepairRunState.SNAPSHOTTED, RepairRunState.BASELINE_RUNNING}:
            await _transition(
                session, run, RepairRunState.BASELINE_RUNNING, actor="executor", reason=ReasonCode.ADMITTED
            )
            spec = _job(runtime, run, dest, "verify", policy.limits.sandbox_seconds)
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
            if baseline.timed_out or baseline.exit_code not in {0, 1}:
                await _transition(
                    session,
                    run,
                    RepairRunState.UNREPRODUCIBLE,
                    actor="executor",
                    reason=ReasonCode.TARGET_NOT_REPRODUCED,
                    detail="baseline supervisor rejected the process",
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
            _maybe_crash(runtime, "reproduced")
        else:
            spec = _job(runtime, run, dest, "verify", policy.limits.sandbox_seconds)
            baseline = await runtime.broker.run_tests(spec)

        if await _cancelled(session, run, runtime):
            return run

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

        snap = Snapshot(
            snapshot_id="current",
            tenant_id=str(run.tenant_id),
            run_id=str(run.id),
            root=dest,
        )
        max_candidates = policy.limits.candidates
        existing = (
            await session.execute(select(Candidate).where(Candidate.run_id == run.id))
        ).scalars().all()
        start_iteration = len(existing) + 1
        last_feedback = ""
        for iteration in range(start_iteration, max_candidates + 1):
            if await _cancelled(session, run, runtime):
                return run
            await _transition(session, run, RepairRunState.DIAGNOSING, actor="agent", reason=ReasonCode.ADMITTED)
            await session.commit()

            router = ToolRouter(
                policy,
                {"current": snap},
                broker=runtime.broker,
                job_factory=lambda stage="explore": _job(runtime, run, dest, stage, policy.limits.sandbox_seconds),
            )
            if runtime.provider_factory is not None:
                provider = runtime.provider_factory(dest, traceback)
            else:
                provider = FixtureProvider(dest, traceback)
            user_trace = traceback if not last_feedback else f"{traceback}\n\nVerifier feedback:\n{last_feedback}"
            outcome = await run_agent(
                provider,
                router,
                tenant_id=str(run.tenant_id),
                run_id=str(run.id),
                traceback=user_trace,
                snapshot_id="current",
                execution_sha=run.execution_sha,
                tests=",".join(sorted(baseline.inventory.failed_ids)),
                model=model or runtime.model_id,
            )
            session.add(
                ModelCall(
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    provider=getattr(provider, "name", provider_name),
                    model=model,
                    prompt_version=outcome.prompt_version,
                    input_tokens=outcome.input_tokens,
                    output_tokens=outcome.output_tokens,
                    cost_usd=0.0,
                )
            )
            runtime.budget.settle(lease.id, 0.0 if outcome.simulated else min(lease.reserved, 0.05))
            run.simulated = outcome.simulated
            if outcome.diagnosis:
                run.diagnosis = outcome.diagnosis.model_dump()
            if not outcome.patch:
                if iteration >= max_candidates:
                    await _transition(
                        session,
                        run,
                        RepairRunState.NO_VALID_PATCH,
                        actor="agent",
                        reason=ReasonCode.NO_VALID_PATCH,
                    )
                    await session.commit()
                    return run
                last_feedback = "no patch submitted"
                continue

            candidate = Candidate(
                tenant_id=run.tenant_id,
                run_id=run.id,
                iteration=iteration,
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
            await _transition(session, run, RepairRunState.PATCH_PROPOSED, actor="agent", reason=ReasonCode.ADMITTED)
            await _transition(session, run, RepairRunState.VERIFYING, actor="verifier", reason=ReasonCode.ADMITTED)
            await session.commit()
            _maybe_crash(runtime, "verifying")

            async def _broker_runner(workdir: Path, extra_args=None, timeout_seconds=120, python_bin=None, env_extra=None):
                spec = _job(runtime, run, workdir, "verify", timeout_seconds)
                return await runtime.broker.run_tests(spec, extra_args)

            verify_root = runtime.work_root / str(run.id) / f"verify-{iteration}"
            result = await averify_candidate(
                dest,
                outcome.patch,
                policy,
                work_root=verify_root,
                timeout_seconds=policy.limits.sandbox_seconds,
                run_tests=_broker_runner,
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
                        "candidate_exit_code": result.candidate.exit_code if result.candidate else None,
                    },
                    limitations=result.limitations,
                )
            )
            run.limitations = result.limitations
            VERIFY.labels(result="verified" if result.verified else "failed").inc()
            if result.flaky:
                await _transition(
                    session,
                    run,
                    RepairRunState.FLAKY_SUSPECTED,
                    actor="verifier",
                    reason=ReasonCode.FLAKY_BASELINE,
                )
                await session.commit()
                await session.refresh(run)
                return run
            if result.verified:
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
            last_feedback = "; ".join(result.errors) or "verification failed"
            if iteration >= max_candidates:
                await _transition(
                    session,
                    run,
                    RepairRunState.NO_VALID_PATCH,
                    actor="verifier",
                    reason=ReasonCode.VERIFICATION_FAILED,
                    detail=last_feedback,
                )
                await session.commit()
                await session.refresh(run)
                return run
            await _transition(
                session,
                run,
                RepairRunState.DIAGNOSING,
                actor="verifier",
                reason=ReasonCode.VERIFICATION_FAILED,
                detail=last_feedback,
            )
            await session.commit()

        await session.refresh(run)
        return run
