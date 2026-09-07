from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tracefix.agent.redact import redact
from tracefix.agent.tools import (
    GetDiffArgs,
    ReadFileArgs,
    RequestTestArgs,
    SearchCodeArgs,
    SubmitPatchArgs,
    parse_tool_call,
)
from tracefix.policy.paths import matches_any, normalize_repo_path
from tracefix.policy.schema import RepositoryPolicy
from tracefix.verification.harness import run_pytest


@dataclass
class Snapshot:
    snapshot_id: str
    tenant_id: str
    run_id: str
    root: Path
    original_diff: str = ""


class ToolRouter:
    def __init__(self, policy: RepositoryPolicy, snapshots: dict[str, Snapshot]) -> None:
        self.policy = policy
        self.snapshots = snapshots
        self.submitted_patch: str | None = None
        self.test_requests: list[RequestTestArgs] = []

    def _snap(self, snapshot_id: str, tenant_id: str, run_id: str) -> Snapshot:
        snap = self.snapshots.get(snapshot_id)
        if snap is None or snap.tenant_id != tenant_id or snap.run_id != run_id:
            raise PermissionError("snapshot is not authorized for this run")
        return snap

    def call(
        self,
        name: str,
        arguments: dict,
        *,
        tenant_id: str,
        run_id: str,
    ) -> str:
        parsed = parse_tool_call(name, arguments)
        if isinstance(parsed, ReadFileArgs):
            return self._read_file(parsed, tenant_id, run_id)
        if isinstance(parsed, SearchCodeArgs):
            return self._search(parsed, tenant_id, run_id)
        if isinstance(parsed, GetDiffArgs):
            snap = self._snap(parsed.snapshot_id, tenant_id, run_id)
            return redact(snap.original_diff or "<no github diff>")
        if isinstance(parsed, SubmitPatchArgs):
            self._snap(parsed.snapshot_id, tenant_id, run_id)
            self.submitted_patch = parsed.unified_diff
            return "patch accepted for validation"
        if isinstance(parsed, RequestTestArgs):
            if parsed.approved_profile_id != self.policy.execution_profile:
                raise PermissionError("profile is not approved")
            self.test_requests.append(parsed)
            snap = next(iter(self.snapshots.values()))
            result = run_pytest(
                snap.root,
                extra_args=parsed.permitted_test_ids or None,
                timeout_seconds=self.policy.limits.sandbox_seconds,
            )
            return redact(result.stdout + "\n" + result.stderr)
        raise PermissionError("tool not permitted")

    def _read_file(self, args: ReadFileArgs, tenant_id: str, run_id: str) -> str:
        snap = self._snap(args.snapshot_id, tenant_id, run_id)
        path = normalize_repo_path(args.relative_path)
        target = (snap.root / path).resolve()
        target.relative_to(snap.root.resolve())
        if not target.is_file():
            return "<missing file>"
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, args.start_line)
        end = min(len(lines), args.end_line)
        excerpt = "\n".join(f"{i}:{lines[i - 1]}" for i in range(start, end + 1))
        return redact(excerpt)

    def _search(self, args: SearchCodeArgs, tenant_id: str, run_id: str) -> str:
        snap = self._snap(args.snapshot_id, tenant_id, run_id)
        hits: list[str] = []
        allowed = args.allowed_paths or self.policy.source_paths
        query = args.query
        for file in snap.root.rglob("*"):
            if not file.is_file():
                continue
            rel = file.relative_to(snap.root).as_posix()
            try:
                normalize_repo_path(rel)
            except ValueError:
                continue
            if allowed and not matches_any(rel, allowed):
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for idx, line in enumerate(text.splitlines(), 1):
                if query in line:
                    hits.append(f"{rel}:{idx}:{line[:200]}")
                    if len(hits) >= args.result_limit:
                        return redact("\n".join(hits))
        return redact("\n".join(hits) or "<no matches>")
