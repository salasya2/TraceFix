from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tracefix.verification.junit import Inventory, parse_junit

PROFILE_PYTHON312_PYTEST_V1 = {
    "id": "python312-pytest-v1",
    "command": [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--junitxml=junit.xml"],
    "env": {
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONHASHSEED": "0",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    },
}

_HOST_ENV_ALLOWLIST = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "USERNAME",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "PYTHONUTF8",
    "PYTHONIOENCODING",
    "SystemRoot",
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


def sandbox_env(env_extra: dict[str, str] | None = None) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in _HOST_ENV_ALLOWLIST:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env.update(PROFILE_PYTHON312_PYTEST_V1["env"])
    if env_extra:
        env.update(env_extra)
    return env


def sanitize_pytest_args(extra_args: list[str] | None) -> list[str]:
    if not extra_args:
        return []
    clean: list[str] = []
    for arg in extra_args:
        if not arg or arg.startswith("-") or "--" in arg:
            raise ValueError(f"pytest option flags are not permitted: {arg!r}")
        if ".." in arg or arg.startswith("/") or arg.startswith("\\"):
            raise ValueError(f"illegal test selector: {arg!r}")
        clean.append(arg)
    return clean


def run_pytest(
    workdir: Path,
    *,
    extra_args: list[str] | None = None,
    timeout_seconds: int = 120,
    python_bin: str | None = None,
    env_extra: dict[str, str] | None = None,
    on_start: Callable[[subprocess.Popen[Any]], None] | None = None,
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
    cmd.extend(sanitize_pytest_args(extra_args))
    env = sandbox_env(env_extra)
    start = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(
        cmd,
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if on_start is not None:
        on_start(proc)
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        code = proc.returncode if proc.returncode is not None else 1
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except Exception:
            stdout, stderr = "", "timeout"
        code = 124
        stdout = stdout[-200_000:] if isinstance(stdout, str) else ""
        stderr = (stderr or "timeout")[-200_000:] if isinstance(stderr, str) else "timeout"
    else:
        stdout = (stdout or "")[-200_000:]
        stderr = (stderr or "")[-200_000:]
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


def result_from_junit(
    workdir: Path,
    *,
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
    duration_ms: int = 0,
    timed_out: bool = False,
) -> HarnessResult:
    junit = workdir / "junit.xml"
    inventory = parse_junit(junit)
    digest = hashlib.sha256(junit.read_bytes()).hexdigest() if junit.exists() else None
    return HarnessResult(
        exit_code=exit_code,
        inventory=inventory,
        stdout=_strip_controls(stdout),
        stderr=_strip_controls(stderr),
        duration_ms=duration_ms,
        junit_digest=digest,
        timed_out=timed_out,
    )


def _strip_controls(text: str) -> str:
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
