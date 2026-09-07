from datetime import datetime, timedelta, timezone

from tracefix.domain.reasons import ReasonCode
from tracefix.policy.admission import AdmissionContext, admit_event
from tracefix.policy.paths import matches_any, normalize_repo_path
from tracefix.policy.patch_policy import validate_patch_text
from tracefix.policy.publication import decide_publication
from tracefix.policy.schema import DEFAULT_POLICY


def test_path_normalization_and_globs():
    assert normalize_repo_path(r"src\\stats.py") == "src/stats.py"
    assert matches_any("src/stats.py", ["src/"])
    assert matches_any("pkg/conftest.py", ["**/conftest.py"])
    assert matches_any("requirements-dev.txt", ["requirements*.txt"])
    try:
        normalize_repo_path("../etc/passwd")
        assert False
    except ValueError:
        pass


def test_admission_rejects_forks_and_bots():
    ctx = AdmissionContext(
        event_type="pull_request",
        is_fork=True,
        workflow_id=1,
        conclusion="failure",
        head_sha="a",
        execution_sha="a",
        checkout_trusted=True,
        language_profile_ok=True,
        bot_generated=False,
        installation_selected=True,
        tenant_suspended=False,
        emergency_stop=False,
    )
    result = admit_event(DEFAULT_POLICY, ctx)
    assert not result.admitted
    assert result.reason == ReasonCode.FORK_PR_UNSUPPORTED
    bot = admit_event(DEFAULT_POLICY, AdmissionContext(**{**ctx.__dict__, "is_fork": False, "bot_generated": True, "event_type": "push"}))
    assert bot.reason == ReasonCode.EVENT_IGNORED


def test_patch_rejects_protected_and_skip():
    decision = validate_patch_text(
        "diff --git a/tests/test.py b/tests/test.py\n+pytest.mark.skip\n",
        DEFAULT_POLICY,
        parsed_files=["tests/test.py"],
        additions=1,
        deletions=0,
        binary_files=[],
        symlink_files=[],
        mode_changes=[],
        applies_cleanly=True,
    )
    assert not decision.accepted
    assert any("protected" in e or "skip" in e for e in decision.errors)


def test_publication_digest_binding():
    now = datetime.now(timezone.utc)
    blocked = decide_publication(
        DEFAULT_POLICY,
        approved=True,
        approval_expires_at=now + timedelta(minutes=10),
        now=now,
        patch_digest="aaa",
        approved_digest="bbb",
        source_sha="s",
        approved_source_sha="s",
        base_sha="b",
        approved_base_sha="b",
        policy_version=1,
        approved_policy_version=1,
        safety_fingerprint_current="x",
        safety_fingerprint_approved="x",
        safety_review_ok=True,
        refs_unchanged=True,
        installation_active=True,
    )
    assert blocked.reason == ReasonCode.APPROVAL_DIGEST_MISMATCH
