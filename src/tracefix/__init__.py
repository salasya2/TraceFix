"""TraceFix control-plane package.

Subpackages live in the spec layout (packages/*, apps/*, services/*).
__path__ is extended so `import tracefix.domain` resolves without a single src tree.
"""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__version__ = "0.1.0"
PINNED_GITHUB_API_VERSION = "2022-11-28"
PINNED_PROMPT_VERSION = "v1"
DEFAULT_MODEL_ID = "claude-sonnet-5"

__path__ = extend_path(__path__, __name__)
_ROOT = Path(__file__).resolve().parents[2]
for _rel in (
    "packages/domain/src/tracefix",
    "packages/policy/src/tracefix",
    "packages/github/src/tracefix",
    "packages/agent/src/tracefix",
    "packages/verification/src/tracefix",
    "packages/storage/src/tracefix",
    "apps/api/src/tracefix",
    "services/orchestrator/src/tracefix",
    "services/executor/src/tracefix",
    "services/publisher/src/tracefix",
    "services/credential_broker/src/tracefix",
):
    _p = _ROOT / _rel
    if _p.is_dir() and str(_p) not in __path__:
        __path__.append(str(_p))
