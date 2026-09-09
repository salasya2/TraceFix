from __future__ import annotations

import asyncio
import shutil
import time

from tracefix.executor.broker import JobSpec, SandboxRuntimeUnavailable
from tracefix.verification.harness import HarnessResult, result_from_junit, sanitize_pytest_args


class DockerAdapter:
    """Linux Docker backend for local isolation experiments.

    Production requires gVisor runsc + RuntimeClass and must fail closed
    if that runtime is unavailable. This adapter never silently claims
    gVisor enforcement and never falls back to the host interpreter.
    """

    image = "python:3.12.8-bookworm"
    runtime: str | None = None

    def __init__(self) -> None:
        self._containers: dict[str, str] = {}

    def _docker(self) -> str:
        docker = shutil.which("docker")
        if not docker:
            raise SandboxRuntimeUnavailable("docker is not available; refusing host fallback")
        return docker

    def _run_cmd(self, docker: str, spec: JobSpec, extra_args: list[str] | None, name: str) -> list[str]:
        cmd = [
            docker,
            "run",
            "--name",
            name,
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
            f"{spec.snapshot}:/work:rw",
            "-w",
            "/work",
        ]
        if self.runtime:
            cmd.extend(["--runtime", self.runtime])
        cmd.extend(
            [
                self.image,
                "python",
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--junitxml=junit.xml",
                "-q",
                "tests",
                *sanitize_pytest_args(extra_args),
            ]
        )
        return cmd

    async def run_tests(
        self, spec: JobSpec, extra_args: list[str] | None = None, sandbox_id: str | None = None
    ) -> HarnessResult:
        docker = self._docker()
        name = f"tf-{(sandbox_id or spec.run_id)[:20]}"
        self._containers[sandbox_id or name] = name
        cmd = self._run_cmd(docker, spec, extra_args, name)
        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timed_out = False
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=spec.timeout_seconds)
            code = proc.returncode if proc.returncode is not None else 1
        except TimeoutError:
            timed_out = True
            proc.kill()
            stdout_b, stderr_b = b"", b"timeout"
            code = 124
            await self.terminate(sandbox_id or name)
        duration_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_b.decode("utf-8", "replace")[-200_000:] if isinstance(stdout_b, bytes) else ""
        stderr = stderr_b.decode("utf-8", "replace")[-200_000:] if isinstance(stderr_b, bytes) else ""
        result = result_from_junit(
            spec.snapshot,
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )
        return result

    async def terminate(self, sandbox_id: str) -> None:
        name = self._containers.pop(sandbox_id, sandbox_id)
        docker = shutil.which("docker")
        if not docker or not name:
            return
        proc = await asyncio.create_subprocess_exec(
            docker, "rm", "-f", name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
