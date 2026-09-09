from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tracefix.github.schemas import DraftPullRequest, WorkflowJob, WorkflowRun


@dataclass
class FixtureRepo:
    owner: str
    name: str
    repo_id: int
    default_branch: str = "main"
    files: dict[str, str] = field(default_factory=dict)  # path@sha -> content
    refs: dict[str, str] = field(default_factory=dict)
    runs: dict[int, WorkflowRun] = field(default_factory=dict)
    jobs: dict[int, list[WorkflowJob]] = field(default_factory=dict)
    logs: dict[tuple[int, int], str] = field(default_factory=dict)
    pulls: list[DraftPullRequest] = field(default_factory=list)
    blobs: dict[str, str] = field(default_factory=dict)
    commits: dict[str, dict[str, Any]] = field(default_factory=dict)


class FixtureGitHub:
    """In-process GitHub used by demo, tests, and labeled simulated runs."""

    def __init__(self) -> None:
        self.repos: dict[str, FixtureRepo] = {}
        self._pr_seq = 1
        self._blob_seq = 1

    def add_repo(self, repo: FixtureRepo) -> None:
        self.repos[f"{repo.owner}/{repo.name}"] = repo

    def _repo(self, owner: str, repo: str) -> FixtureRepo:
        key = f"{owner}/{repo}"
        if key not in self.repos:
            raise KeyError(key)
        return self.repos[key]

    async def get_workflow_run(
        self, owner: str, repo: str, run_id: int, *, attempt: int | None = None
    ) -> WorkflowRun:
        run = self._repo(owner, repo).runs[run_id]
        if attempt is not None and run.run_attempt != attempt:
            return run.model_copy(update={"run_attempt": attempt})
        return run

    async def list_jobs(
        self, owner: str, repo: str, run_id: int, *, attempt: int
    ) -> list[WorkflowJob]:
        return list(self._repo(owner, repo).jobs.get(run_id, []))

    async def get_run_logs(self, owner: str, repo: str, run_id: int, *, attempt: int) -> str:
        return self._repo(owner, repo).logs.get((run_id, attempt), "")

    async def get_ref(self, owner: str, repo: str, ref: str) -> str:
        repo_obj = self._repo(owner, repo)
        if ref in repo_obj.refs:
            return repo_obj.refs[ref]
        alt = ref if ref.startswith("refs/") else f"refs/heads/{ref}"
        if alt in repo_obj.refs:
            return repo_obj.refs[alt]
        raise KeyError(ref)

    async def get_file(self, owner: str, repo: str, path: str, *, ref: str) -> bytes:
        repo_obj = self._repo(owner, repo)
        sha = repo_obj.refs.get(ref, ref)
        key = f"{path}@{sha}"
        if key in repo_obj.files:
            return repo_obj.files[key].encode("utf-8")
        # fall back to unversioned fixture content
        for stored, content in repo_obj.files.items():
            if stored.startswith(path + "@") or stored == path:
                return content.encode("utf-8")
        raise FileNotFoundError(path)

    async def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> None:
        repo_obj = self._repo(owner, repo)
        if ref in repo_obj.refs:
            raise RuntimeError("ref already exists")
        repo_obj.refs[ref] = sha

    async def create_blob(self, owner: str, repo: str, content: str) -> str:
        sha = f"blob{self._blob_seq:04d}"
        self._blob_seq += 1
        self._repo(owner, repo).blobs[sha] = content
        return sha

    async def create_tree(
        self, owner: str, repo: str, base_tree: str, entries: list[dict[str, Any]]
    ) -> str:
        sha = f"tree{self._blob_seq:04d}"
        self._blob_seq += 1
        self._repo(owner, repo).commits[sha] = {"base": base_tree, "entries": entries}
        return sha

    async def create_commit(
        self, owner: str, repo: str, message: str, tree: str, parents: list[str]
    ) -> str:
        sha = f"cmt{self._blob_seq:04d}"
        self._blob_seq += 1
        self._repo(owner, repo).commits[sha] = {
            "message": message,
            "tree": tree,
            "parents": parents,
        }
        return sha

    async def update_ref(
        self, owner: str, repo: str, ref: str, sha: str, *, force: bool = False
    ) -> None:
        if force:
            raise RuntimeError("force-push is forbidden")
        repo_obj = self._repo(owner, repo)
        repo_obj.refs[ref] = sha

    async def create_pull(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = True,
    ) -> DraftPullRequest:
        existing = await self.find_pull_by_head(owner, repo, head)
        if existing:
            return existing
        pr = DraftPullRequest(
            number=self._pr_seq,
            html_url=f"https://github.com/{owner}/{repo}/pull/{self._pr_seq}",
            head=head,
            base=base,
            draft=draft,
            title=title,
            body=body,
        )
        self._pr_seq += 1
        self._repo(owner, repo).pulls.append(pr)
        return pr

    async def find_pull_by_head(self, owner: str, repo: str, head: str) -> DraftPullRequest | None:
        for pr in self._repo(owner, repo).pulls:
            if pr.head == head:
                return pr
        return None
