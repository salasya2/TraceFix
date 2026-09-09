from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from tracefix.verification.harness import HarnessResult


class SandboxRuntimeUnavailable(RuntimeError):
    """Admission must fail closed. Never silently fall back to an unenforced runtime."""


@dataclass
class JobSpec:
    tenant_id: str
    run_id: str
    capability: str
    source_digest: str
    image_digest: str
    dependency_bundle_digest: str
    profile_id: str
    stage: str
    snapshot: Path
    timeout_seconds: int = 300
    memory_mib: int = 4096
    pids: int = 256
    disk_mib: int = 2048
    expiry: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10))

    def validate(self) -> None:
        if self.stage not in {"prep", "explore", "verify"}:
            raise ValueError("unknown stage")
        if not self.capability:
            raise ValueError("missing execution capability")
        if ".." in str(self.snapshot):
            raise ValueError("illegal snapshot path")


class ExecutorAdapter(Protocol):
    async def run_tests(
        self, spec: JobSpec, extra_args: list[str] | None = None, sandbox_id: str | None = None
    ) -> HarnessResult: ...

    async def terminate(self, sandbox_id: str) -> None: ...


@dataclass
class SandboxLease:
    sandbox_id: str
    spec: JobSpec
    created_at: datetime
    cleaned: bool = False


class ExecutionBroker:
    def __init__(self, adapter: ExecutorAdapter) -> None:
        self.adapter = adapter
        self.leases: dict[str, SandboxLease] = {}
        self.emergency_stop = False
        self.tenant_stops: set[str] = set()

    def issue_capability(self, tenant_id: str, run_id: str, stage: str) -> str:
        return f"cap:{tenant_id}:{run_id}:{stage}:{uuid.uuid4()}"

    def _admit(self, spec: JobSpec) -> None:
        spec.validate()
        if self.emergency_stop:
            raise RuntimeError("executor stop switch engaged")
        if spec.tenant_id in self.tenant_stops:
            raise RuntimeError("executor stop switch engaged")
        if datetime.now(timezone.utc) > spec.expiry:
            raise RuntimeError("execution capability expired")

    async def run_tests(self, spec: JobSpec, extra_args: list[str] | None = None) -> HarnessResult:
        self._admit(spec)
        sandbox_id = f"sbx-{uuid.uuid4()}"
        self.leases[sandbox_id] = SandboxLease(sandbox_id, spec, datetime.now(timezone.utc))
        try:
            return await self.adapter.run_tests(spec, extra_args, sandbox_id=sandbox_id)
        finally:
            await self.terminate(sandbox_id)

    async def terminate(self, sandbox_id: str) -> None:
        lease = self.leases.get(sandbox_id)
        if lease and not lease.cleaned:
            await self.adapter.terminate(sandbox_id)
            lease.cleaned = True

    async def terminate_run(self, run_id: str) -> int:
        killed = 0
        for lease in list(self.leases.values()):
            if lease.spec.run_id == run_id and not lease.cleaned:
                await self.terminate(lease.sandbox_id)
                killed += 1
        return killed

    def engage_tenant_stop(self, tenant_id: str) -> None:
        self.tenant_stops.add(tenant_id)

    def clear_tenant_stop(self, tenant_id: str) -> None:
        self.tenant_stops.discard(tenant_id)

    async def sweep(self) -> int:
        cleaned = 0
        now = datetime.now(timezone.utc)
        for lease in list(self.leases.values()):
            if not lease.cleaned and now > lease.spec.expiry:
                await self.terminate(lease.sandbox_id)
                cleaned += 1
        return cleaned
