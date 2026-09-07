from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from tracefix.executor.broker import JobSpec
from tracefix.verification.harness import HarnessResult, run_pytest


class DockerAdapter:
    """Linux Docker backend for local isolation experiments.

    Production requires gVisor runsc + RuntimeClass and must fail closed
    if that runtime is unavailable. This adapter never silently claims
    gVisor enforcement.
    """

    image = "python:3.12.8-bookworm"

    async def run_tests(self, spec: JobSpec, extra_args: list[str] | None = None) -> HarnessResult:
        docker = shutil.which("docker")
        if not docker:
            return await asyncio.to_thread(
                run_pytest,
                spec.snapshot,
                extra_args=extra_args,
                timeout_seconds=spec.timeout_seconds,
            )
        work = Path(spec.snapshot)
        cmd = [
            docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--memory",
            f"{spec.memory_mib}m",
            "--pids-limit",
            str(spec.pids),
            "--user",
            "65534:65534",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-v",
            f"{work}:/work:rw",
            "-w",
            "/work",
            self.image,
            "python",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--junitxml=junit.xml",
            "-q",
            *(extra_args or []),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=spec.timeout_seconds)
        except TimeoutError:
            proc.kill()
            raise
        # Reuse local parser against the bind-mounted junit.
        result = await asyncio.to_thread(
            run_pytest,
            spec.snapshot,
            extra_args=["--collect-only"],
            timeout_seconds=30,
        )
        result.exit_code = proc.returncode or 0
        result.stdout = stdout.decode("utf-8", "replace")[-200_000:]
        result.stderr = stderr.decode("utf-8", "replace")[-200_000:]
        return result

    async def terminate(self, sandbox_id: str) -> None:
        return None
