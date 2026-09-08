from __future__ import annotations

import hashlib
import json


def workflow_safety_fingerprint(
    *,
    workflow_files: dict[str, str],
    reusable_action_pins: dict[str, str],
    runner_labels: list[str],
    token_permissions: dict[str, str],
    privileged_runners: bool,
) -> str:
    payload = json.dumps(
        {
            "workflows": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in sorted(workflow_files.items())},
            "actions": reusable_action_pins,
            "runners": runner_labels,
            "permissions": token_permissions,
            "privileged": privileged_runners,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def publication_safe(
    *,
    fingerprint: str,
    approved_fingerprint: str | None,
    pull_request_target: bool,
    workflow_run_on_tracefix: bool,
    secrets_on_fork: bool,
    privileged_runners: bool,
) -> tuple[bool, str]:
    if pull_request_target or workflow_run_on_tracefix or secrets_on_fork or privileged_runners:
        return False, "unsafe downstream workflow configuration"
    if approved_fingerprint and fingerprint != approved_fingerprint:
        return False, "safety fingerprint changed"
    if not approved_fingerprint:
        return False, "workflow safety cannot be established"
    return True, "admitted"
