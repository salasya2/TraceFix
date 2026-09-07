from __future__ import annotations

import asyncio

from tracefix.executor.broker import JobSpec
from tracefix.verification.harness import HarnessResult, run_pytest


class ProcessAdapter:
    """Local developer backend. Not the production hostile-code boundary."""

    async def run_tests(self, spec: JobSpec, extra_args: list[str] | None = None) -> HarnessResult:
        return await asyncio.to_thread(
            run_pytest,
            spec.snapshot,
            extra_args=extra_args,
            timeout_seconds=spec.timeout_seconds,
        )

    async def terminate(self, sandbox_id: str) -> None:
        return None
