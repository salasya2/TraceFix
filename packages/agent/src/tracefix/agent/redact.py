from __future__ import annotations

import re

_SECRET = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*([^\s'\"\\]+)"
)
_KEY_BLOB = re.compile(r"(?i)\b(sk-|ghp_|ghs_|xai-)[A-Za-z0-9_\-]{8,}")


def redact(text: str, *, max_chars: int = 40_000) -> str:
    cleaned = "".join(ch if ch in "\n\t" or ord(ch) >= 32 else " " for ch in text)
    cleaned = _SECRET.sub(r"\1=<redacted>", cleaned)
    cleaned = _KEY_BLOB.sub("<redacted>", cleaned)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n<truncated>"
    return cleaned
