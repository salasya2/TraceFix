from __future__ import annotations

from tracefix.domain.states import RepairRunState, TerminalStates

_FORWARD: dict[RepairRunState, frozenset[RepairRunState]] = {
    RepairRunState.RECEIVED: frozenset(
        {
            RepairRunState.ADMITTED,
            RepairRunState.IGNORED,
            RepairRunState.UNSUPPORTED,
            RepairRunState.POLICY_BLOCKED,
            RepairRunState.CANCELLED,
            RepairRunState.SYSTEM_ERROR,
        }
    ),
    RepairRunState.ADMITTED: frozenset(
        {
            RepairRunState.SNAPSHOTTED,
            RepairRunState.UNSUPPORTED,
            RepairRunState.POLICY_BLOCKED,
            RepairRunState.BUDGET_EXCEEDED,
            RepairRunState.CANCELLED,
            RepairRunState.EXPIRED,
            RepairRunState.SYSTEM_ERROR,
        }
    ),
    RepairRunState.SNAPSHOTTED: frozenset(
        {
            RepairRunState.BASELINE_RUNNING,
            RepairRunState.UNSUPPORTED,
            RepairRunState.CANCELLED,
            RepairRunState.SYSTEM_ERROR,
        }
    ),
    RepairRunState.BASELINE_RUNNING: frozenset(
        {
            RepairRunState.REPRODUCED,
            RepairRunState.UNREPRODUCIBLE,
            RepairRunState.FLAKY_SUSPECTED,
            RepairRunState.UNSUPPORTED,
            RepairRunState.CANCELLED,
            RepairRunState.SYSTEM_ERROR,
            RepairRunState.BUDGET_EXCEEDED,
        }
    ),
    RepairRunState.REPRODUCED: frozenset(
        {
            RepairRunState.DIAGNOSING,
            RepairRunState.BUDGET_EXCEEDED,
            RepairRunState.CANCELLED,
            RepairRunState.SYSTEM_ERROR,
        }
    ),
    RepairRunState.DIAGNOSING: frozenset(
        {
            RepairRunState.PATCH_PROPOSED,
            RepairRunState.NO_VALID_PATCH,
            RepairRunState.BUDGET_EXCEEDED,
            RepairRunState.CANCELLED,
            RepairRunState.SYSTEM_ERROR,
            RepairRunState.DIAGNOSING,
        }
    ),
    RepairRunState.PATCH_PROPOSED: frozenset(
        {
            RepairRunState.VERIFYING,
            RepairRunState.NO_VALID_PATCH,
            RepairRunState.CANCELLED,
            RepairRunState.SYSTEM_ERROR,
        }
    ),
    RepairRunState.VERIFYING: frozenset(
        {
            RepairRunState.AWAITING_APPROVAL,
            RepairRunState.DIAGNOSING,
            RepairRunState.NO_VALID_PATCH,
            RepairRunState.FLAKY_SUSPECTED,
            RepairRunState.BUDGET_EXCEEDED,
            RepairRunState.CANCELLED,
            RepairRunState.SYSTEM_ERROR,
        }
    ),
    RepairRunState.AWAITING_APPROVAL: frozenset(
        {
            RepairRunState.PUBLISHING,
            RepairRunState.PATCH_DOWNLOAD_READY,
            RepairRunState.STALE,
            RepairRunState.EXPIRED,
            RepairRunState.CANCELLED,
            RepairRunState.POLICY_BLOCKED,
        }
    ),
    RepairRunState.PUBLISHING: frozenset(
        {
            RepairRunState.PR_OPENED,
            RepairRunState.PATCH_DOWNLOAD_READY,
            RepairRunState.STALE,
            RepairRunState.POLICY_BLOCKED,
            RepairRunState.SYSTEM_ERROR,
            RepairRunState.CANCELLED,
        }
    ),
}


def allowed_transition(current: RepairRunState, nxt: RepairRunState) -> bool:
    if current == nxt:
        return True
    if current in TerminalStates:
        return False
    return nxt in _FORWARD.get(current, frozenset())
