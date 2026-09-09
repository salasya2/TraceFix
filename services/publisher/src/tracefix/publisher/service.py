from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from tracefix.domain.reasons import ReasonCode
from tracefix.github.client import GitHubClient
from tracefix.policy.publication import decide_publication
from tracefix.policy.schema import RepositoryPolicy
from tracefix.verification.apply import apply_unified_diff
from tracefix.verification.diff import parse_unified_diff


@dataclass
class PublishRequest:
    tenant_id: UUID
    repository_id: UUID
    candidate_id: UUID
    run_id: UUID
    github_run_id: int
    github_attempt: int
    owner: str
    repo: str
    patch: str
    patch_digest: str
    source_sha: str
    base_sha: str
    policy_version: int
    evidence_id: UUID
    diagnosis_markdown: str
    verification_markdown: str
    safety_ok: bool
    safety_fingerprint: str | None
    approved_fingerprint: str | None
    refs_unchanged: bool
    installation_active: bool
    approved: bool
    approval_expires_at: datetime | None
    approved_digest: str | None
    approved_source_sha: str | None
    approved_base_sha: str | None
    approved_policy_version: int | None
    existing_lock: str | None = None
    tree_digest: str | None = None


@dataclass
class PublishResult:
    mode: str
    reason: ReasonCode
    detail: str
    operation_id: str
    lock_key: str
    branch: str | None = None
    pr_url: str | None = None
    pr_number: int | None = None
    patch_artifact: bool = False
    commit_sha: str | None = None


class Publisher:
    def __init__(self, github: GitHubClient, locks: dict[str, str] | None = None) -> None:
        self.github = github
        self._locks: dict[str, str] = locks if locks is not None else {}
        self._ops: dict[str, PublishResult] = {}

    def lock_key(self, tenant_id: UUID, repo_id: UUID, run_id: int, attempt: int) -> str:
        return f"{tenant_id}:{repo_id}:{run_id}:{attempt}"

    async def publish(self, policy: RepositoryPolicy, req: PublishRequest) -> PublishResult:
        now = datetime.now(timezone.utc)
        decision = decide_publication(
            policy,
            approved=req.approved,
            approval_expires_at=req.approval_expires_at,
            now=now,
            patch_digest=req.patch_digest,
            approved_digest=req.approved_digest,
            source_sha=req.source_sha,
            approved_source_sha=req.approved_source_sha,
            base_sha=req.base_sha,
            approved_base_sha=req.approved_base_sha,
            policy_version=req.policy_version,
            approved_policy_version=req.approved_policy_version,
            safety_fingerprint_current=req.safety_fingerprint,
            safety_fingerprint_approved=req.approved_fingerprint,
            safety_review_ok=req.safety_ok,
            refs_unchanged=req.refs_unchanged,
            installation_active=req.installation_active,
        )
        lock = self.lock_key(req.tenant_id, req.repository_id, req.github_run_id, req.github_attempt)
        if lock in self._locks:
            existing = self._ops[self._locks[lock]]
            return existing
        operation_id = f"pub-{uuid4()}"
        if not decision.allowed and decision.mode == "blocked":
            result = PublishResult(decision.mode, decision.reason, decision.detail, operation_id, lock)
            return result
        if decision.mode == "patch_download":
            result = PublishResult(
                "patch_download",
                decision.reason,
                decision.detail,
                operation_id,
                lock,
                patch_artifact=True,
            )
            self._locks[lock] = operation_id
            self._ops[operation_id] = result
            return result
        branch = f"tracefix/run-{req.github_run_id}-attempt-{req.github_attempt}"
        existing_pr = await self.github.find_pull_by_head(req.owner, req.repo, branch)
        if existing_pr:
            result = PublishResult(
                "draft_pr",
                ReasonCode.PUBLICATION_RECONCILED,
                "existing PR returned",
                operation_id,
                lock,
                branch=branch,
                pr_url=existing_pr.html_url,
                pr_number=existing_pr.number,
            )
            self._locks[lock] = operation_id
            self._ops[operation_id] = result
            return result
        commit_sha = await self._commit_patch(req, branch)
        body = self._pr_body(req)
        pr = await self.github.create_pull(
            req.owner,
            req.repo,
            title=f"fix: TraceFix repair for run {req.github_run_id}",
            body=body,
            head=branch,
            base="main",
            draft=True,
        )
        result = PublishResult(
            "draft_pr",
            ReasonCode.PUBLISHED,
            "draft pull request opened",
            operation_id,
            lock,
            branch=branch,
            pr_url=pr.html_url,
            pr_number=pr.number,
            commit_sha=commit_sha,
        )
        self._locks[lock] = operation_id
        self._ops[operation_id] = result
        return result

    async def _commit_patch(self, req: PublishRequest, branch: str) -> str:
        parsed = parse_unified_diff(req.patch)
        if parsed.errors or not parsed.files:
            raise RuntimeError("refusing to publish a patch that does not describe file changes")
        tmp = Path(tempfile.mkdtemp(prefix="tracefix-pub-"))
        try:
            for file_diff in parsed.files:
                path = file_diff.path
                if file_diff.old_path == "/dev/null":
                    continue
                try:
                    content = await self.github.get_file(req.owner, req.repo, path, ref=req.source_sha)
                except FileNotFoundError:
                    continue
                target = tmp / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            apply_unified_diff(tmp, req.patch)
            entries: list[dict] = []
            for file_diff in parsed.files:
                path = file_diff.path
                target = tmp / path
                if not target.exists():
                    entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                    continue
                blob_sha = await self.github.create_blob(req.owner, req.repo, target.read_text(encoding="utf-8"))
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob_sha, "content": target.read_text(encoding="utf-8")})
            tree = await self.github.create_tree(req.owner, req.repo, req.source_sha, entries)
            commit_sha = await self.github.create_commit(
                req.owner,
                req.repo,
                f"fix: TraceFix repair for run {req.github_run_id}",
                tree,
                [req.source_sha],
            )
            ref = f"refs/heads/{branch}"
            try:
                await self.github.create_ref(req.owner, req.repo, ref, req.source_sha)
            except Exception:
                pass
            await self.github.update_ref(req.owner, req.repo, ref, commit_sha)
            return commit_sha
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

    def _pr_body(self, req: PublishRequest) -> str:
        return (
            "## TraceFix proposed repair\n\n"
            "This change was generated by TraceFix, an AI investigation service.\n\n"
            f"- Failed GitHub Actions run: `{req.github_run_id}` attempt `{req.github_attempt}`\n"
            f"- Source SHA: `{req.source_sha}`\n"
            f"- Base SHA: `{req.base_sha}`\n"
            f"- Patch digest: `{req.patch_digest}`\n"
            f"- Policy version: `{req.policy_version}`\n\n"
            "### Diagnosis\n"
            f"{req.diagnosis_markdown}\n\n"
            "### Verification\n"
            f"{req.verification_markdown}\n\n"
            "Human review is required. TraceFix does not merge this branch.\n"
        )
