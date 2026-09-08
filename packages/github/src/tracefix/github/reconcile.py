from __future__ import annotations

from dataclasses import dataclass

from tracefix.github.fixture import FixtureGitHub
from tracefix.github.schemas import WorkflowRun


@dataclass
class ReconcileCursor:
    seen_run_ids: set[int]


def reconcile_failed_runs(
    github: FixtureGitHub, owner: str, repo: str, cursor: ReconcileCursor
) -> list[WorkflowRun]:
    """Overlapping cursor: re-scan known runs plus any new failures.

    GitHub does not automatically redeliver failed webhook deliveries.
    """
    repo_obj = github._repo(owner, repo)
    found: list[WorkflowRun] = []
    for run in repo_obj.runs.values():
        if run.conclusion == "failure" and run.id not in cursor.seen_run_ids:
            found.append(run)
        cursor.seen_run_ids.add(run.id)
    return found
