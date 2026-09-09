from pathlib import Path

from tracefix._paths import ROOT
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.verification.harness import HarnessResult
from tracefix.verification.junit import Inventory
from tracefix.verification.pipeline import verify_candidate

TASK = ROOT / "evals" / "tasks" / "tf001-off-by-one"


def test_post_report_crash_is_not_verified(tmp_path: Path):
    good = (TASK / "EXPECTED.patch").read_text(encoding="utf-8")
    calls = {"n": 0}

    def runner(workdir: Path, **_kwargs):
        calls["n"] += 1
        from tracefix.verification.harness import run_pytest

        result = run_pytest(workdir, timeout_seconds=30)
        patched = "len(nums) - 1" not in (workdir / "src" / "stats.py").read_text(encoding="utf-8")
        if patched:
            return HarnessResult(
                exit_code=7,
                inventory=result.inventory,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=result.duration_ms,
                junit_digest=result.junit_digest,
                timed_out=False,
            )
        return result

    outcome = verify_candidate(TASK, good, DEFAULT_POLICY, work_root=tmp_path / "crash", run_tests=runner)
    assert outcome.verified is False
    assert outcome.badge == "none"
    assert any("exit 7" in err for err in outcome.errors)


def test_timeout_is_not_verified(tmp_path: Path):
    good = (TASK / "EXPECTED.patch").read_text(encoding="utf-8")

    def runner(workdir: Path, **_kwargs):
        from tracefix.verification.harness import run_pytest

        result = run_pytest(workdir, timeout_seconds=30)
        patched = "len(nums) - 1" not in (workdir / "src" / "stats.py").read_text(encoding="utf-8")
        if patched:
            return HarnessResult(
                exit_code=124,
                inventory=result.inventory,
                stdout=result.stdout,
                stderr="timeout",
                duration_ms=result.duration_ms,
                junit_digest=result.junit_digest,
                timed_out=True,
            )
        return result

    outcome = verify_candidate(TASK, good, DEFAULT_POLICY, work_root=tmp_path / "timeout", run_tests=runner)
    assert outcome.verified is False
    assert any("timed out" in err for err in outcome.errors)


def test_missing_junit_is_not_verified(tmp_path: Path):
    good = (TASK / "EXPECTED.patch").read_text(encoding="utf-8")

    def runner(workdir: Path, **_kwargs):
        from tracefix.verification.harness import run_pytest

        result = run_pytest(workdir, timeout_seconds=30)
        patched = "len(nums) - 1" not in (workdir / "src" / "stats.py").read_text(encoding="utf-8")
        if patched:
            return HarnessResult(
                exit_code=0,
                inventory=Inventory([], 0, ["missing junit xml"]),
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=1,
                junit_digest=None,
                timed_out=False,
            )
        return result

    outcome = verify_candidate(TASK, good, DEFAULT_POLICY, work_root=tmp_path / "empty", run_tests=runner)
    assert outcome.verified is False
    assert any("junit" in err for err in outcome.errors)


def test_pytest_option_flags_rejected():
    from tracefix.verification.harness import sanitize_pytest_args

    try:
        sanitize_pytest_args(["-k", "test_average"])
        assert False
    except ValueError:
        pass
    assert sanitize_pytest_args(["tests/test_stats.py::test_average"]) == ["tests/test_stats.py::test_average"]
