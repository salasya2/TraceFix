from __future__ import annotations

import shutil

from tracefix.executor.broker import JobSpec
from tracefix.verification.harness import HarnessResult


class SandboxRuntimeUnavailable(RuntimeError):
    """Admission must fail closed. Never silently fall back to runc."""


class GVisorAdapter:
    """Production hostile-code backend.

    Requires an explicit RuntimeClass (`runsc`) and verified network
    enforcement. Ordinary Docker is not this adapter.
    """

    runtime_class = "gvisor"
    handler = "runsc"

    def __init__(self, *, runtime_available: bool | None = None) -> None:
        if runtime_available is None:
            runtime_available = shutil.which("runsc") is not None
        self.runtime_available = runtime_available

    async def run_tests(self, spec: JobSpec, extra_args: list[str] | None = None) -> HarnessResult:
        if not self.runtime_available:
            raise SandboxRuntimeUnavailable(
                "gVisor runsc/RuntimeClass unavailable; refusing to schedule hostile execution"
            )
        raise SandboxRuntimeUnavailable(
            "this host is not the dedicated Linux execution pool; job not scheduled"
        )

    async def terminate(self, sandbox_id: str) -> None:
        return None
