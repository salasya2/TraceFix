from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tracefix._paths import ROOT, ensure_src_on_path

ensure_src_on_path()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tracefix")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap")
    sub.add_parser("dev")
    sub.add_parser("serve")
    sub.add_parser("demo")
    sub.add_parser("lint")
    t = sub.add_parser("test")
    t.add_argument("suite", choices=["unit", "integration", "security", "e2e", "chaos", "all"], nargs="?", default="unit")
    ev = sub.add_parser("eval")
    ev.add_argument("--split", default="development")
    ev.add_argument("--output", default="artifacts/evaluation.json")
    sub.add_parser("build")
    sub.add_parser("verify-staging")
    args = parser.parse_args(argv)
    return {
        "bootstrap": cmd_bootstrap,
        "dev": lambda: asyncio.run(cmd_demo(serve=True)),
        "serve": lambda: asyncio.run(cmd_serve()),
        "demo": lambda: asyncio.run(cmd_demo(serve=False)),
        "lint": cmd_lint,
        "test": lambda: cmd_test(args.suite),
        "eval": lambda: cmd_eval(args.split, args.output),
        "build": cmd_build,
        "verify-staging": cmd_verify_staging,
    }[args.cmd]()


def cmd_bootstrap() -> int:
    print("TraceFix bootstrap")
    print(f"  python: {sys.version.split()[0]}")
    print(f"  root:   {ROOT}")
    missing = []
    for name in ("python",):
        if shutil.which(name) is None:
            missing.append(name)
    docker = shutil.which("docker")
    print(f"  docker: {docker or 'not found (process executor will be used)'}")
    (ROOT / ".data").mkdir(exist_ok=True)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    env = ROOT / ".env"
    if not env.exists():
        shutil.copy(ROOT / ".env.example", env)
        print("  wrote .env from .env.example")
    if shutil.which("uv"):
        subprocess.check_call(["uv", "sync", "--extra", "dev"], cwd=ROOT)
    else:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], cwd=ROOT)
    print("bootstrap ok")
    if missing:
        print("missing:", ", ".join(missing))
        return 1
    return 0


def cmd_lint() -> int:
    ruff = [sys.executable, "-m", "ruff", "check", "packages", "apps", "services", "tests", "src", "scripts"]
    code = subprocess.call(ruff, cwd=ROOT)
    web = ROOT / "apps" / "web"
    if (web / "package.json").exists() and shutil.which("cmd"):
        ts = subprocess.call(["cmd", "/c", "pnpm", "exec", "tsc", "--noEmit"], cwd=web)
        code = code or ts
    return code


def cmd_test(suite: str) -> int:
    mapping = {
        "unit": ["tests/unit"],
        "integration": ["tests/integration"],
        "security": ["tests/security"],
        "e2e": ["tests/e2e"],
        "chaos": ["tests/chaos"],
        "all": ["tests"],
    }
    return subprocess.call([sys.executable, "-m", "pytest", "-q", *mapping[suite]], cwd=ROOT)


def cmd_eval(split: str, output: str) -> int:
    from evals.runner.run_eval import run_eval

    path = ROOT / output
    path.parent.mkdir(parents=True, exist_ok=True)
    report = run_eval(split)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("wrote", path)
    return 0


def cmd_build() -> int:
    compose = ROOT / "deploy" / "local" / "docker-compose.yml"
    if not compose.exists():
        print("compose file missing")
        return 1
    if not shutil.which("docker"):
        print("docker not available; images not built")
        return 0
    return subprocess.call(["docker", "compose", "-f", str(compose), "build"], cwd=ROOT)


def cmd_verify_staging() -> int:
    print("Staging verification requires the production Linux/gVisor pool.")
    print("Local substitute: pytest tests/security tests/integration")
    return cmd_test("security")


async def cmd_serve() -> int:
    import uvicorn

    from tracefix.api.app import create_app
    from tracefix.demo import build_context

    ctx = await build_context()
    app = create_app(ctx)
    print("API http://127.0.0.1:8080")
    config = uvicorn.Config(app, host="127.0.0.1", port=8080, log_level="info")
    await uvicorn.Server(config).serve()
    return 0


async def cmd_demo(serve: bool = False) -> int:
    from tracefix.demo import run_demo

    return await run_demo(serve=serve)


if __name__ == "__main__":
    raise SystemExit(main())
