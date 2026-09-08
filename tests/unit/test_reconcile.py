from tracefix.github.fixture import FixtureGitHub, FixtureRepo
from tracefix.github.reconcile import ReconcileCursor, reconcile_failed_runs
from tracefix.github.schemas import WorkflowRun


def test_missed_webhook_discovered_without_duplicate():
    gh = FixtureGitHub()
    run = WorkflowRun(
        id=9,
        name="t",
        head_sha="abc",
        event="push",
        status="completed",
        conclusion="failure",
        run_attempt=1,
    )
    gh.add_repo(FixtureRepo("acme", "stats", 1, runs={9: run}))
    cursor = ReconcileCursor(set())
    first = reconcile_failed_runs(gh, "acme", "stats", cursor)
    second = reconcile_failed_runs(gh, "acme", "stats", cursor)
    assert [r.id for r in first] == [9]
    assert second == []
