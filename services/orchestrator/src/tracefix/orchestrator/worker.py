from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from tracefix.factory import build_app_context
from tracefix.orchestrator.workflow import RepairInvestigationWorkflow, bind_worker, investigate_activity
from tracefix.settings import load_settings


async def run_worker() -> None:
    settings = load_settings()
    if settings.orchestrator != "temporal":
        raise SystemExit("TRACEFIX_ORCHESTRATOR=temporal is required for this worker")
    ctx = await build_app_context(settings)
    bind_worker(ctx.runtime)
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue="tracefix-repair",
        workflows=[RepairInvestigationWorkflow],
        activities=[investigate_activity],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
