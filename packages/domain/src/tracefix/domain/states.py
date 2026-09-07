from __future__ import annotations

from enum import StrEnum


class RepairRunState(StrEnum):
    RECEIVED = "RECEIVED"
    ADMITTED = "ADMITTED"
    SNAPSHOTTED = "SNAPSHOTTED"
    BASELINE_RUNNING = "BASELINE_RUNNING"
    REPRODUCED = "REPRODUCED"
    DIAGNOSING = "DIAGNOSING"
    PATCH_PROPOSED = "PATCH_PROPOSED"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PUBLISHING = "PUBLISHING"
    PR_OPENED = "PR_OPENED"
    PATCH_DOWNLOAD_READY = "PATCH_DOWNLOAD_READY"
    IGNORED = "IGNORED"
    UNSUPPORTED = "UNSUPPORTED"
    UNREPRODUCIBLE = "UNREPRODUCIBLE"
    FLAKY_SUSPECTED = "FLAKY_SUSPECTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    NO_VALID_PATCH = "NO_VALID_PATCH"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


TerminalStates = frozenset(
    {
        RepairRunState.PR_OPENED,
        RepairRunState.PATCH_DOWNLOAD_READY,
        RepairRunState.IGNORED,
        RepairRunState.UNSUPPORTED,
        RepairRunState.UNREPRODUCIBLE,
        RepairRunState.FLAKY_SUSPECTED,
        RepairRunState.POLICY_BLOCKED,
        RepairRunState.NO_VALID_PATCH,
        RepairRunState.BUDGET_EXCEEDED,
        RepairRunState.STALE,
        RepairRunState.EXPIRED,
        RepairRunState.CANCELLED,
        RepairRunState.SYSTEM_ERROR,
    }
)

ACTIVE_INVESTIGATION_STATES = frozenset(
    {
        RepairRunState.ADMITTED,
        RepairRunState.SNAPSHOTTED,
        RepairRunState.BASELINE_RUNNING,
        RepairRunState.REPRODUCED,
        RepairRunState.DIAGNOSING,
        RepairRunState.PATCH_PROPOSED,
        RepairRunState.VERIFYING,
    }
)
