from pathlib import Path

from tracefix.verification.harness import run_pytest


def test_infinite_loop_terminates(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_loop.py").write_text(
        "def test_loop():\n    while True:\n        pass\n",
        encoding="utf-8",
    )
    result = run_pytest(tmp_path, timeout_seconds=2)
    assert result.timed_out or result.exit_code != 0
