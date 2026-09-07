from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    login: str
    id: int | None = None


class GitHubRepo(BaseModel):
    id: int
    full_name: str
    default_branch: str = "main"
    fork: bool = False
    html_url: str | None = None


class GitHubInstallation(BaseModel):
    id: int
    account: GitHubUser | None = None


class WorkflowRun(BaseModel):
    id: int
    name: str | None = None
    head_sha: str
    event: str
    status: str
    conclusion: str | None = None
    html_url: str | None = None
    run_attempt: int = 1
    head_branch: str | None = None
    workflow_id: int | None = None
    pull_requests: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowJob(BaseModel):
    id: int
    name: str
    conclusion: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowRunEvent(BaseModel):
    action: str
    workflow_run: WorkflowRun
    repository: GitHubRepo
    installation: GitHubInstallation | None = None
    sender: GitHubUser | None = None


class DraftPullRequest(BaseModel):
    number: int
    html_url: str
    head: str
    base: str
    draft: bool = True
    title: str
    body: str
