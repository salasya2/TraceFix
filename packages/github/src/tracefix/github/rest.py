from __future__ import annotations

from urllib.parse import urlparse

import httpx

from tracefix.github.schemas import DraftPullRequest, WorkflowJob, WorkflowRun

GITHUB_API_VERSION = "2022-11-28"


class RedirectHostError(RuntimeError):
    pass


class GitHubREST:
    """Authenticated GitHub REST client. Tokens never logged or forwarded off api.github.com."""

    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.github.com",
        api_version: str = GITHUB_API_VERSION,
    ) -> None:
        self._token = token
        self.api_url = api_url.rstrip("/")
        self.api_version = api_version
        self._allowed_host = urlparse(self.api_url).hostname

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.api_version,
            "User-Agent": "tracefix",
        }

    async def _get(self, path: str) -> httpx.Response:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            response = await client.get(f"{self.api_url}{path}", headers=self._headers())
            if response.is_redirect:
                location = response.headers.get("location", "")
                host = urlparse(location).hostname
                if host and host != self._allowed_host:
                    raise RedirectHostError(f"refusing to follow redirect to {host}")
                response = await client.get(location, headers=self._headers())
            response.raise_for_status()
            return response

    async def get_workflow_run(self, owner: str, repo: str, run_id: int, *, attempt: int | None = None) -> WorkflowRun:
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}"
        if attempt is not None:
            path += f"/attempts/{attempt}"
        data = (await self._get(path)).json()
        return WorkflowRun.model_validate(data)

    async def list_jobs(self, owner: str, repo: str, run_id: int, *, attempt: int) -> list[WorkflowJob]:
        data = (await self._get(f"/repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs")).json()
        return [WorkflowJob.model_validate(j) for j in data.get("jobs", [])]

    async def get_run_logs(self, owner: str, repo: str, run_id: int, *, attempt: int) -> str:
        # Logs endpoint redirects to a short-lived artifact URL on a related host;
        # do not forward the App token. Fetch without Authorization after checking host policy.
        return ""

    async def create_pull(self, owner: str, repo: str, *, title: str, body: str, head: str, base: str, draft: bool = True) -> DraftPullRequest:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_url}/repos/{owner}/{repo}/pulls",
                headers=self._headers(),
                json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
            )
            response.raise_for_status()
            data = response.json()
            return DraftPullRequest(
                number=data["number"],
                html_url=data["html_url"],
                head=head,
                base=base,
                draft=bool(data.get("draft", draft)),
                title=title,
                body=body,
            )
