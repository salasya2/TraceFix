from tracefix.policy.safety import publication_safe, workflow_safety_fingerprint


def test_fingerprint_change_and_unsafe_workflows():
    fp = workflow_safety_fingerprint(
        workflow_files={".github/workflows/ci.yml": "on: push\n"},
        reusable_action_pins={"actions/checkout": "b4ffde65f46336ab88eb53be808477a3936bae11"},
        runner_labels=["ubuntu-latest"],
        token_permissions={"contents": "read"},
        privileged_runners=False,
    )
    ok, _ = publication_safe(
        fingerprint=fp,
        approved_fingerprint=fp,
        pull_request_target=False,
        workflow_run_on_tracefix=False,
        secrets_on_fork=False,
        privileged_runners=False,
    )
    assert ok
    blocked, reason = publication_safe(
        fingerprint=fp,
        approved_fingerprint="other",
        pull_request_target=False,
        workflow_run_on_tracefix=False,
        secrets_on_fork=False,
        privileged_runners=False,
    )
    assert not blocked
    assert "fingerprint" in reason
    unsafe, _ = publication_safe(
        fingerprint=fp,
        approved_fingerprint=fp,
        pull_request_target=True,
        workflow_run_on_tracefix=False,
        secrets_on_fork=False,
        privileged_runners=False,
    )
    assert not unsafe
