from __future__ import annotations

from pathlib import Path

from tracefix.github.fixture import FixtureGitHub


async def materialize_fixture_snapshot(
    github: FixtureGitHub, owner: str, repo: str, sha: str, dest: Path
) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    repo_obj = github._repo(owner, repo)
    written: set[str] = set()
    for key, content in repo_obj.files.items():
        if "@" in key:
            path, ref = key.rsplit("@", 1)
            if ref not in {sha, "main", repo_obj.refs.get("main", "")} and ref != sha:
                continue
        else:
            path = key
        if path in written:
            continue
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.add(path)
    return dest
