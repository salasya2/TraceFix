from __future__ import annotations

from dataclasses import dataclass, field

from tracefix.policy.paths import matches_any, normalize_repo_path
from tracefix.policy.schema import RepositoryPolicy

_SKIP_MARKERS = (
    "pytest.mark.skip",
    "@unittest.skip",
    "sys.exit(0)",
    "pytest.main([])",
)
_HARNESS_MARKERS = (
    "conftest.py",
    "PYTEST_ADDOPTS",
    "pytest_configure",
    "pytest_collection_modifyitems",
)
_EXFIL_MARKERS = (
    "socket.socket",
    "urllib.request",
    "requests.get",
    "httpx.",
    "subprocess.Popen",
    "os.system",
    "eval(",
    "exec(",
    "__import__('os')",
)


@dataclass
class PatchDecision:
    accepted: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    changed_lines: int = 0
    additions: int = 0
    deletions: int = 0


def validate_patch_text(
    diff_text: str,
    policy: RepositoryPolicy,
    *,
    parsed_files: list[str],
    additions: int,
    deletions: int,
    binary_files: list[str],
    symlink_files: list[str],
    mode_changes: list[str],
    applies_cleanly: bool,
) -> PatchDecision:
    errors: list[str] = []
    warnings: list[str] = []
    normalized: list[str] = []
    for path in parsed_files:
        try:
            normalized.append(normalize_repo_path(path))
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
    for path in binary_files:
        errors.append(f"{path}: binary files are not allowed")
    for path in symlink_files:
        errors.append(f"{path}: symlink changes are not allowed")
    for path in mode_changes:
        errors.append(f"{path}: file mode changes are not allowed")
    if not applies_cleanly:
        errors.append("hunks do not apply cleanly")
    if not normalized and not errors:
        errors.append("patch is empty")
    if len(normalized) > policy.limits.changed_files:
        errors.append(
            f"changed files {len(normalized)} exceed limit {policy.limits.changed_files}"
        )
    changed_lines = additions + deletions
    if changed_lines > policy.limits.changed_lines:
        errors.append(
            f"changed lines {changed_lines} exceed limit {policy.limits.changed_lines}"
        )
    for path in normalized:
        if matches_any(path, policy.protected_paths):
            errors.append(f"{path}: protected path")
        if policy.source_paths and not matches_any(path, policy.source_paths):
            errors.append(f"{path}: outside allowed source_paths")
    lowered = diff_text.lower()
    if any(marker.lower() in lowered for marker in _SKIP_MARKERS):
        errors.append("patch appears to skip tests or suppress execution")
    if any(marker.lower() in lowered for marker in _HARNESS_MARKERS):
        errors.append("patch appears to alter test harness behavior")
    if any(marker.lower() in lowered for marker in _EXFIL_MARKERS):
        warnings.append("patch contains potentially dangerous network or exec primitives")
    return PatchDecision(
        accepted=not errors,
        errors=errors,
        warnings=warnings,
        changed_files=normalized,
        changed_lines=changed_lines,
        additions=additions,
        deletions=deletions,
    )
