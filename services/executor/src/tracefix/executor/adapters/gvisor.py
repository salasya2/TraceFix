from __future__ import annotations

import shutil

from tracefix.executor.adapters.docker import DockerAdapter
from tracefix.executor.broker import JobSpec, SandboxRuntimeUnavailable
from tracefix.verification.harness import HarnessResult

__all__ = ["GVisorAdapter", "SandboxRuntimeUnavailable"]


class GVisorAdapter(DockerAdapter):
    """Production hostile-code backend.

    Requires an explicit RuntimeClass (`runsc`) and verified network
    enforcement. Ordinary Docker is not this adapter.
    """

    runtime_class = "gvisor"
    handler = "runsc"
    runtime = "runsc"

    def __init__(self, *, runtime_available: bool | None = None) -> None:
        super().__init__()
        if runtime_available is None:
            runtime_available = shutil.which("runsc") is not None
        self.runtime_available = runtime_available

    async def run_tests(
        self, spec: JobSpec, extra_args: list[str] | None = None, sandbox_id: str | None = None
    ) -> HarnessResult:
        if not self.runtime_available:
            raise SandboxRuntimeUnavailable(
                "gVisor runsc/RuntimeClass unavailable; refusing to schedule hostile execution"
            )
        return await super().run_tests(spec, extra_args, sandbox_id=sandbox_id)
