from __future__ import annotations

from pathlib import Path

from tracefix.policy.paths import normalize_repo_path
from tracefix.verification.diff import ParsedDiff, parse_unified_diff


class PatchApplyError(ValueError):
    pass


def apply_unified_diff(root: Path, diff_text: str) -> list[str]:
    parsed = parse_unified_diff(diff_text)
    if parsed.errors:
        raise PatchApplyError("; ".join(parsed.errors))
    changed: list[str] = []
    for file_diff in parsed.files:
        path = normalize_repo_path(file_diff.path)
        target = (root / path).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise PatchApplyError(f"path escape {path}") from exc
        if file_diff.new_path == "/dev/null":
            if target.exists():
                target.unlink()
            changed.append(path)
            continue
        original = ""
        if target.exists():
            original = target.read_text(encoding="utf-8")
        updated = _apply_hunks(original, file_diff.hunks, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(updated, encoding="utf-8", newline="\n")
        changed.append(path)
    return changed


def _apply_hunks(original: str, hunks, path: str) -> str:
    source = original.splitlines()
    cursor = 0
    out: list[str] = []
    for hunk in hunks:
        old_index = hunk.old_start - 1
        if old_index < 0:
            old_index = 0
        if old_index < cursor:
            raise PatchApplyError(f"{path}: overlapping hunks")
        out.extend(source[cursor:old_index])
        cursor = old_index
        for line in hunk.lines:
            if line.startswith(" "):
                expected = line[1:]
                if cursor >= len(source) or source[cursor] != expected:
                    raise PatchApplyError(f"{path}: context mismatch at line {cursor + 1}")
                out.append(source[cursor])
                cursor += 1
            elif line.startswith("-"):
                expected = line[1:]
                if cursor >= len(source) or source[cursor] != expected:
                    raise PatchApplyError(f"{path}: deletion mismatch at line {cursor + 1}")
                cursor += 1
            elif line.startswith("+"):
                out.append(line[1:])
            elif line.startswith("\\"):
                continue
            else:
                raise PatchApplyError(f"{path}: illegal hunk line")
    out.extend(source[cursor:])
    return "\n".join(out) + ("\n" if original.endswith("\n") or not original else "\n")


def diff_applies_cleanly(root: Path, parsed: ParsedDiff) -> bool:
    try:
        for file_diff in parsed.files:
            path = normalize_repo_path(file_diff.path)
            target = root / path
            original = target.read_text(encoding="utf-8") if target.exists() else ""
            _apply_hunks(original, file_diff.hunks, path)
        return True
    except (PatchApplyError, ValueError, OSError):
        return False
