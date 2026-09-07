"""Ensure spec-layout source trees are importable during editable/dev runs."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIRS = [
    _ROOT / "src",
    _ROOT / "packages" / "domain" / "src",
    _ROOT / "packages" / "policy" / "src",
    _ROOT / "packages" / "github" / "src",
    _ROOT / "packages" / "agent" / "src",
    _ROOT / "packages" / "verification" / "src",
    _ROOT / "packages" / "storage" / "src",
    _ROOT / "apps" / "api" / "src",
    _ROOT / "services" / "orchestrator" / "src",
    _ROOT / "services" / "executor" / "src",
    _ROOT / "services" / "publisher" / "src",
    _ROOT / "services" / "credential_broker" / "src",
]


def ensure_src_on_path() -> Path:
    for path in _SRC_DIRS:
        text = str(path)
        if path.is_dir() and text not in sys.path:
            sys.path.insert(0, text)
    return _ROOT


ROOT = ensure_src_on_path()
