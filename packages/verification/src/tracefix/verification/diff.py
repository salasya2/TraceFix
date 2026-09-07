from __future__ import annotations

import re
from dataclasses import dataclass, field

_FILE_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
_OLD_RE = re.compile(r"^--- (?:a/)?(.+)$")
_NEW_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


@dataclass
class FileDiff:
    old_path: str
    new_path: str
    is_binary: bool = False
    is_symlink: bool = False
    mode_change: str | None = None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path if self.new_path != "/dev/null" else self.old_path

    @property
    def additions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.startswith("+") and not line.startswith("+++"))

    @property
    def deletions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.startswith("-") and not line.startswith("---"))


@dataclass
class ParsedDiff:
    files: list[FileDiff]
    errors: list[str] = field(default_factory=list)

    @property
    def paths(self) -> list[str]:
        return [f.path for f in self.files]

    @property
    def additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def binary_files(self) -> list[str]:
        return [f.path for f in self.files if f.is_binary]

    @property
    def symlink_files(self) -> list[str]:
        return [f.path for f in self.files if f.is_symlink]

    @property
    def mode_changes(self) -> list[str]:
        return [f.path for f in self.files if f.mode_change]


def parse_unified_diff(text: str) -> ParsedDiff:
    if "\x00" in text:
        return ParsedDiff([], errors=["binary/null bytes in diff"])
    files: list[FileDiff] = []
    errors: list[str] = []
    current: FileDiff | None = None
    hunk: Hunk | None = None
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            current = None
            hunk = None
            match = _FILE_RE.match(raw)
            if not match:
                errors.append(f"malformed diff header: {raw}")
                continue
            current = FileDiff(old_path=match.group(1), new_path=match.group(2))
            files.append(current)
            continue
        if current is None:
            continue
        if raw.startswith("GIT binary patch") or raw.startswith("Binary files "):
            current.is_binary = True
            continue
        if raw.startswith("new file mode ") or raw.startswith("old mode ") or raw.startswith("new mode "):
            current.mode_change = raw
            continue
        if "new mode 120000" in raw or "old mode 120000" in raw:
            current.is_symlink = True
        if raw.startswith("--- "):
            match = _OLD_RE.match(raw)
            if match:
                current.old_path = match.group(1).strip()
            continue
        if raw.startswith("+++ "):
            match = _NEW_RE.match(raw)
            if match:
                current.new_path = match.group(1).strip()
            continue
        if raw.startswith("@@ "):
            match = _HUNK_RE.match(raw)
            if not match:
                errors.append(f"malformed hunk header: {raw}")
                continue
            hunk = Hunk(
                old_start=int(match.group(1)),
                old_count=int(match.group(2) or "1"),
                new_start=int(match.group(3)),
                new_count=int(match.group(4) or "1"),
                lines=[],
            )
            current.hunks.append(hunk)
            continue
        if hunk is not None and (raw.startswith(" ") or raw.startswith("+") or raw.startswith("-") or raw == "\\"):
            hunk.lines.append(raw)
            continue
        if hunk is not None and raw.startswith("\\"):
            continue
    return ParsedDiff(files=files, errors=errors)
