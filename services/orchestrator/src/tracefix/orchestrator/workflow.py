"""Temporal workflow definition. Activities wrap InvestigationRuntime.

Local demo uses runner.run_investigation directly. Production workers
register this workflow against a Temporal namespace.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

try:
    from temporalio import activity, workflow
except ImportError:  # pragma: no cover
    activity = None
    workflow = None


if workflow is not None:

    @activity.defn
    async def investigate_activity(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    @workflow.defn
    class RepairInvestigationWorkflow:
        @workflow.run
        async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
            return await workflow.execute_activity(
                investigate_activity,
                payload,
                start_to_close_timeout=timedelta(minutes=20),
            )
