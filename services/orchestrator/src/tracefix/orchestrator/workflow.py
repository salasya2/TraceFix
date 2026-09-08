"""Temporal workflow definition. Activities wrap InvestigationRuntime.

Local demo uses runner.run_investigation directly. Production workers
register this workflow against a Temporal namespace. Workflow IDs are
stable so a crashed dispatcher recovers the existing execution.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from tracefix.orchestrator.runner import InvestigationRuntime, run_investigation
from tracefix.policy.schema import RepositoryPolicy

try:
    from temporalio import activity, workflow
    from temporalio.common import RetryPolicy
except ImportError:  # pragma: no cover
    activity = None
    workflow = None
    RetryPolicy = None  # type: ignore[misc,assignment]

_RUNTIME: InvestigationRuntime | None = None
_SNAPSHOTS: dict[str, Any] = {}


def bind_worker(runtime: InvestigationRuntime, snapshots: dict[str, Any] | None = None) -> None:
    global _RUNTIME, _SNAPSHOTS
    _RUNTIME = runtime
    _SNAPSHOTS = snapshots or {}


if workflow is not None:

    @activity.defn(name="tracefix.investigate")
    async def investigate_activity(payload: dict[str, Any]) -> dict[str, Any]:
        if _RUNTIME is None:
            raise RuntimeError("worker runtime is not bound")
        run_id = UUID(payload["run_id"])
        snapshot = payload["snapshot"]
        policy = RepositoryPolicy.model_validate(payload["policy"])
        run = await run_investigation(
            _RUNTIME,
            run_id,
            snapshot=__import__("pathlib").Path(snapshot),
            policy=policy,
            traceback=payload.get("traceback", ""),
        )
        return {"run_id": str(run.id), "state": run.state}

    @workflow.defn(name="RepairInvestigationWorkflow")
    class RepairInvestigationWorkflow:
        @workflow.run
        async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
            return await workflow.execute_activity(
                investigate_activity,
                payload,
                start_to_close_timeout=timedelta(minutes=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

else:  # pragma: no cover
    RepairInvestigationWorkflow = None  # type: ignore[misc,assignment]
    investigate_activity = None  # type: ignore[misc,assignment]
