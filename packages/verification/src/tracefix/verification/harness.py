from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tracefix.verification.junit import Inventory, parse_junit

PROFILE_PYTHON312_PYTEST_V1 = {
    "id": "python312-pytest-v1",
    "command": [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--junitxml=junit.xml"],
    "env": {
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONHASHSEED": "0",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    },
}


@dataclass
class HarnessResult:
    exit_code: int
    inventory: Inventory
    stdout: str
    stderr: str
    duration_ms: int
    junit_digest: str | None
    timed_out: bool = False
    extra: dict = field(default_factory=dict)


def run_pytest(
    workdir: Path,
    *,
    extra_args: list[str] | None = None,
    timeout_seconds: int = 120,
    python_bin: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> HarnessResult:
    python = python_bin or sys.executable
    junit = workdir / "junit.xml"
    if junit.exists():
        junit.unlink()
    isolated_ini = workdir / ".tracefix-pytest.ini"
    if not isolated_ini.exists():
        isolated_ini.write_text("[pytest]\n", encoding="utf-8")
    cmd = [
        python,
        "-m",
        "pytest",
        "--rootdir",
        str(workdir),
        "-c",
        str(isolated_ini),
        "-p",
        "no:cacheprovider",
        "--junitxml=junit.xml",
        "-q",
        "tests",
    ]
    if extra_args:
        cmd.extend(extra_args)
    env = os.environ.copy()
    env.update(PROFILE_PYTHON312_PYTEST_V1["env"])
    if env_extra:
        env.update(env_extra)
    env.pop("TRACEFIX_SECRET_KEY", None)
    env.pop("GITHUB_WEBHOOK_SECRET", None)
    env.pop("XAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("AWS_SECRET_ACCESS_KEY", None)
    import time

    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            check=False,
        )
        code = proc.returncode
        stdout = proc.stdout[-200_000:]
        stderr = proc.stderr[-200_000:]
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        code = 124
        stdout = (exc.stdout or "")[-200_000:] if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "")[-200_000:] if isinstance(exc.stderr, str) else "timeout"
    duration_ms = int((time.monotonic() - start) * 1000)
    inventory = parse_junit(junit)
    digest = None
    if junit.exists():
        digest = hashlib.sha256(junit.read_bytes()).hexdigest()
    return HarnessResult(
        exit_code=code,
        inventory=inventory,
        stdout=_strip_controls(stdout),
        stderr=_strip_controls(stderr),
        duration_ms=duration_ms,
        junit_digest=digest,
        timed_out=timed_out,
    )


def _strip_controls(text: str) -> str:
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
