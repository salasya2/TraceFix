"""Developer entrypoint used by Taskfile.yml."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
for rel in [
    "packages/domain/src",
    "packages/policy/src",
    "packages/github/src",
    "packages/agent/src",
    "packages/verification/src",
    "packages/storage/src",
    "apps/api/src",
    "services/orchestrator/src",
    "services/executor/src",
    "services/publisher/src",
    "services/credential_broker/src",
]:
    sys.path.insert(0, str(ROOT / rel))

from tracefix.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
