from __future__ import annotations

from typing import Any, Protocol

from tracefix.github.schemas import DraftPullRequest, WorkflowJob, WorkflowRun


class GitHubClient(Protocol):
    async def get_workflow_run(
        self, owner: str, repo: str, run_id: int, *, attempt: int | None = None
    ) -> WorkflowRun: ...

    async def list_jobs(
        self, owner: str, repo: str, run_id: int, *, attempt: int
    ) -> list[WorkflowJob]: ...

    async def get_run_logs(self, owner: str, repo: str, run_id: int, *, attempt: int) -> str: ...

    async def get_file(
        self, owner: str, repo: str, path: str, *, ref: str
    ) -> bytes: ...

    async def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> None: ...

    async def create_blob(self, owner: str, repo: str, content: str) -> str: ...

    async def create_tree(
        self, owner: str, repo: str, base_tree: str, entries: list[dict[str, Any]]
    ) -> str: ...

    async def create_commit(
        self, owner: str, repo: str, message: str, tree: str, parents: list[str]
    ) -> str: ...

    async def update_ref(self, owner: str, repo: str, ref: str, sha: str, *, force: bool = False) -> None: ...

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
    ) -> DraftPullRequest: ...

    async def find_pull_by_head(self, owner: str, repo: str, head: str) -> DraftPullRequest | None: ...
