from __future__ import annotations

import posixpath
import re
from fnmatch import fnmatch


def normalize_repo_path(path: str) -> str:
    raw = path.replace("\\", "/").strip()
    if raw.startswith("./"):
        raw = raw[2:]
    while "//" in raw:
        raw = raw.replace("//", "/")
    if raw.startswith("/"):
        raise ValueError("absolute paths are not allowed")
    normalized = posixpath.normpath(raw)
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        raise ValueError("path escapes repository root")
    if normalized == ".":
        raise ValueError("empty path")
    return normalized


def _match_one(path: str, pattern: str) -> bool:
    path = normalize_repo_path(path)
    pattern = pattern.replace("\\", "/").strip()
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if "**" in pattern:
        regex = _glob_to_regex(pattern)
        return re.fullmatch(regex, path) is not None
    if "/" not in pattern:
        return fnmatch(posixpath.basename(path), pattern) or fnmatch(path, pattern)
    return fnmatch(path, pattern)


def _glob_to_regex(pattern: str) -> str:
    out: list[str] = ["^"]
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        ch = pattern[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return "".join(out)


def matches_any(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        try:
            if _match_one(path, pattern):
                return True
        except ValueError:
            return False
    return False
