from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tracefix._paths import ROOT
from tracefix.github.fixture import FixtureGitHub, FixtureRepo
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.publisher.service import PublishRequest, Publisher

TASK = ROOT / "evals" / "tasks" / "tf001-off-by-one"
PATCH = (TASK / "EXPECTED.patch").read_text(encoding="utf-8")
SOURCE = (TASK / "src" / "stats.py").read_text(encoding="utf-8")


async def test_publication_timeout_does_not_open_second_pr():
    gh = FixtureGitHub()
    sha = "sha"
    gh.add_repo(
        FixtureRepo(
            "acme",
            "stats",
            1,
            files={"src/stats.py@sha": SOURCE, "src/stats.py": SOURCE},
            refs={"main": sha, sha: sha},
        )
    )
    pub = Publisher(gh)
    now = datetime.now(timezone.utc)
    req = PublishRequest(
        tenant_id=uuid4(),
        repository_id=uuid4(),
        candidate_id=uuid4(),
        run_id=uuid4(),
        github_run_id=1001,
        github_attempt=1,
        owner="acme",
        repo="stats",
        patch=PATCH,
        patch_digest="abc",
        source_sha=sha,
        base_sha=sha,
        policy_version=1,
        evidence_id=uuid4(),
        diagnosis_markdown="d",
        verification_markdown="v",
        safety_ok=True,
        safety_fingerprint="fp",
        approved_fingerprint="fp",
        refs_unchanged=True,
        installation_active=True,
        approved=True,
        approval_expires_at=now + timedelta(minutes=10),
        approved_digest="abc",
        approved_source_sha=sha,
        approved_base_sha=sha,
        approved_policy_version=1,
    )
    first = await pub.publish(DEFAULT_POLICY, req)
    second = await pub.publish(DEFAULT_POLICY, req)
    assert first.pr_number == second.pr_number
    assert len(gh.repos["acme/stats"].pulls) == 1
    repo = gh.repos["acme/stats"]
    branch = first.branch
    assert repo.refs[f"refs/heads/{branch}"] != sha
    assert repo.blobs
    assert first.commit_sha
