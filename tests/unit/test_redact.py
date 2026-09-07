from tracefix.agent.redact import redact
from tracefix.agent.tools import parse_tool_call


def test_redacts_secrets_and_rejects_unknown_tools():
    text = "Authorization: Bearer sk-abc123456789 and token=ghp_secretvalue"
    out = redact(text)
    assert "sk-abc" not in out
    assert "ghp_secretvalue" not in out
    try:
        parse_tool_call("run_shell", {"cmd": "id"})
        assert False
    except ValueError:
        pass
