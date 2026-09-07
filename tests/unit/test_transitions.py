from tracefix.domain.states import RepairRunState
from tracefix.domain.transitions import allowed_transition


def test_happy_path_and_terminals():
    assert allowed_transition(RepairRunState.RECEIVED, RepairRunState.ADMITTED)
    assert allowed_transition(RepairRunState.VERIFYING, RepairRunState.DIAGNOSING)
    assert not allowed_transition(RepairRunState.PR_OPENED, RepairRunState.RECEIVED)
    assert not allowed_transition(RepairRunState.RECEIVED, RepairRunState.PR_OPENED)
