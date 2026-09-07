from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceProvenance:
    head_sha: str
    base_sha: str | None
    execution_sha: str
    trusted: bool
    detail: str


def resolve_provenance(
    *,
    event: str,
    head_sha: str,
    execution_sha: str | None,
    base_sha: str | None,
    merge_sha: str | None,
    custom_checkout: bool,
) -> SourceProvenance:
    """Record head, base, and execution SHAs separately.

    Never assume head_sha alone proves what GitHub Actions executed.
    """
    if custom_checkout and not execution_sha:
        return SourceProvenance(
            head_sha=head_sha,
            base_sha=base_sha,
            execution_sha=head_sha,
            trusted=False,
            detail="custom checkout without trusted provenance manifest",
        )
    if event == "pull_request":
        exec_sha = execution_sha or merge_sha
        if not exec_sha:
            return SourceProvenance(head_sha, base_sha, head_sha, False, "missing merge/execution sha")
        return SourceProvenance(
            head_sha=head_sha,
            base_sha=base_sha,
            execution_sha=exec_sha,
            trusted=True,
            detail="approved same-repository merge composition",
        )
    exec_sha = execution_sha or head_sha
    return SourceProvenance(
        head_sha=head_sha,
        base_sha=base_sha or head_sha,
        execution_sha=exec_sha,
        trusted=True,
        detail="default-branch push",
    )
