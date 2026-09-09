from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from tracefix.github.schemas import DraftPullRequest, WorkflowJob, WorkflowRun

GITHUB_API_VERSION = "2022-11-28"
_LOG_HOSTS = {
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github.com",
}


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

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            response = await client.request(method, f"{self.api_url}{path}", headers=self._headers(), **kwargs)
            if response.is_redirect:
                location = response.headers.get("location", "")
                host = urlparse(location).hostname
                if host and host != self._allowed_host:
                    raise RedirectHostError(f"refusing to follow redirect to {host}")
                response = await client.request(method, location, headers=self._headers())
            response.raise_for_status()
            return response

    async def _get(self, path: str) -> httpx.Response:
        return await self._request("GET", path)

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
        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            response = await client.get(
                f"{self.api_url}/repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt}/logs",
                headers=self._headers(),
            )
            if not response.is_redirect:
                response.raise_for_status()
                return response.text
            location = response.headers.get("location", "")
            host = urlparse(location).hostname or ""
            if host not in _LOG_HOSTS and host != self._allowed_host:
                raise RedirectHostError(f"refusing to follow log redirect to {host}")
            # Never forward the App token to the artifact host.
            downloaded = await client.get(location)
            downloaded.raise_for_status()
            return downloaded.text

    async def get_file(self, owner: str, repo: str, path: str, *, ref: str) -> bytes:
        response = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )
        data = response.json()
        if data.get("encoding") == "base64":
            import base64

            return base64.b64decode(data["content"])
        download = data.get("download_url")
        if download:
            async with httpx.AsyncClient(timeout=30) as client:
                raw = await client.get(download)
                raw.raise_for_status()
                return raw.content
        raise FileNotFoundError(path)

    async def get_ref(self, owner: str, repo: str, ref: str) -> str:
        trimmed = ref.removeprefix("refs/")
        data = (await self._get(f"/repos/{owner}/{repo}/git/ref/{trimmed}")).json()
        return data["object"]["sha"]

    async def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> None:
        await self._request("POST", f"/repos/{owner}/{repo}/git/refs", json={"ref": ref, "sha": sha})

    async def create_blob(self, owner: str, repo: str, content: str) -> str:
        data = (
            await self._request(
                "POST",
                f"/repos/{owner}/{repo}/git/blobs",
                json={"content": content, "encoding": "utf-8"},
            )
        ).json()
        return data["sha"]

    async def create_tree(
        self, owner: str, repo: str, base_tree: str, entries: list[dict[str, Any]]
    ) -> str:
        data = (
            await self._request(
                "POST",
                f"/repos/{owner}/{repo}/git/trees",
                json={"base_tree": base_tree, "tree": entries},
            )
        ).json()
        return data["sha"]

    async def create_commit(
        self, owner: str, repo: str, message: str, tree: str, parents: list[str]
    ) -> str:
        data = (
            await self._request(
                "POST",
                f"/repos/{owner}/{repo}/git/commits",
                json={"message": message, "tree": tree, "parents": parents},
            )
        ).json()
        return data["sha"]

    async def update_ref(self, owner: str, repo: str, ref: str, sha: str, *, force: bool = False) -> None:
        if force:
            raise RuntimeError("force-push is forbidden")
        trimmed = ref.removeprefix("refs/")
        await self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/git/refs/{trimmed}",
            json={"sha": sha, "force": False},
        )

    async def create_pull(
        self, owner: str, repo: str, *, title: str, body: str, head: str, base: str, draft: bool = True
    ) -> DraftPullRequest:
        response = await self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
        )
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

    async def find_pull_by_head(self, owner: str, repo: str, head: str) -> DraftPullRequest | None:
        data = (
            await self._get(f"/repos/{owner}/{repo}/pulls?state=open&head={owner}:{head}")
        ).json()
        if not data:
            return None
        item = data[0]
        return DraftPullRequest(
            number=item["number"],
            html_url=item["html_url"],
            head=head,
            base=item.get("base", {}).get("ref", "main"),
            draft=bool(item.get("draft", True)),
            title=item.get("title", ""),
            body=item.get("body") or "",
        )
