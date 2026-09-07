from pathlib import Path

from tracefix.agent.router import Snapshot, ToolRouter
from tracefix.policy.schema import DEFAULT_POLICY


def test_malicious_log_cannot_grant_shell(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x=1\n", encoding="utf-8")
    router = ToolRouter(
        DEFAULT_POLICY,
        {"current": Snapshot("current", "t1", "r1", tmp_path)},
    )
    try:
        router.call("run_shell", {"cmd": "curl http://169.254.169.254"}, tenant_id="t1", run_id="r1")
        assert False
    except ValueError:
        pass
    try:
        router.call("read_file", {"snapshot_id": "other", "relative_path": "src/a.py"}, tenant_id="t1", run_id="r1")
        assert False
    except PermissionError:
        pass
    text = router.call(
        "read_file",
        {"snapshot_id": "current", "relative_path": "src/a.py", "start_line": 1, "end_line": 10},
        tenant_id="t1",
        run_id="r1",
    )
    assert "x=1" in text
