from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from tracefix.executor.broker import JobSpec
from tracefix.verification.harness import HarnessResult, run_pytest


class ProcessAdapter:
    """Local developer backend. Not the production hostile-code boundary."""

    def __init__(self) -> None:
        self._procs: dict[str, subprocess.Popen[Any]] = {}

    async def run_tests(
        self, spec: JobSpec, extra_args: list[str] | None = None, sandbox_id: str | None = None
    ) -> HarnessResult:
        sid = sandbox_id or spec.run_id

        def on_start(proc: subprocess.Popen[Any]) -> None:
            self._procs[sid] = proc

        try:
            return await asyncio.to_thread(
                run_pytest,
                spec.snapshot,
                extra_args=extra_args,
                timeout_seconds=spec.timeout_seconds,
                on_start=on_start,
            )
        finally:
            self._procs.pop(sid, None)

    async def terminate(self, sandbox_id: str) -> None:
        proc = self._procs.get(sandbox_id)
        if proc is not None and proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            self._procs.pop(sandbox_id, None)
