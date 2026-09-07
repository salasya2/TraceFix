from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tracefix.api.auth import Principal
from tracefix.domain.roles import Role
from tracefix.github.fixture import FixtureGitHub, FixtureRepo
from tracefix.github.schemas import WorkflowJob, WorkflowRun
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.storage.models import Installation, Membership, Repository, RepositoryPolicyRow, Tenant

TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = UUID("11111111-1111-1111-1111-111111111111")
USER_B = UUID("22222222-2222-2222-2222-222222222222")
REPO_ID = UUID("33333333-3333-3333-3333-333333333333")
INSTALL_ID = UUID("44444444-4444-4444-4444-444444444444")


def principals() -> dict[str, Principal]:
    return {
        "maintainer@tracefix.local": Principal(
            USER_A, TENANT_A, "maintainer@tracefix.local", Role.OWNER, "owner-a"
        ),
        "viewer@tracefix.local": Principal(
            uuid4(), TENANT_A, "viewer@tracefix.local", Role.VIEWER, "viewer-a"
        ),
        "other@tracefix.local": Principal(
            USER_B, TENANT_B, "other@tracefix.local", Role.OWNER, "owner-b"
        ),
    }


async def seed_world(sessions: async_sessionmaker[AsyncSession], github: FixtureGitHub, fixture_root: Path) -> None:
    async with sessions() as session:
        already = await session.get(Tenant, TENANT_A) is not None
        if not already:
            session.add(Tenant(id=TENANT_A, name="Acme", slug="acme", status="active"))
            session.add(Tenant(id=TENANT_B, name="OtherCo", slug="other", status="active"))
            await session.flush()
            session.add(
                Membership(
                    tenant_id=TENANT_A, subject="owner-a", email="maintainer@tracefix.local", role="owner"
                )
            )
            session.add(Membership(tenant_id=TENANT_B, subject="owner-b", email="other@tracefix.local", role="owner"))
            session.add(
                Installation(
                    id=INSTALL_ID,
                    tenant_id=TENANT_A,
                    github_installation_id=9001,
                    account_login="acme",
                    status="active",
                )
            )
            await session.flush()
            session.add(
                Repository(
                    id=REPO_ID,
                    tenant_id=TENANT_A,
                    installation_id=INSTALL_ID,
                    github_repo_id=4242,
                    full_name="acme/stats",
                    selected=True,
                    mode="approval_required",
                    publication_mode="draft_pr",
                    safety_fingerprint="fixture-safe",
                )
            )
            await session.flush()
            session.add(
                RepositoryPolicyRow(
                    tenant_id=TENANT_A,
                    repository_id=REPO_ID,
                    version=1,
                    document=DEFAULT_POLICY.dump(),
                    approver_id=USER_A,
                )
            )
        await session.commit()

    files = {}
    sha = "deadbeefcafebabe"
    for path in fixture_root.rglob("*"):
        if path.is_file():
            rel = path.relative_to(fixture_root).as_posix()
            files[f"{rel}@{sha}"] = path.read_text(encoding="utf-8")
            files[rel] = path.read_text(encoding="utf-8")
    github.add_repo(
        FixtureRepo(
            owner="acme",
            name="stats",
            repo_id=4242,
            files=files,
            refs={"main": sha, sha: sha},
            runs={
                1001: WorkflowRun(
                    id=1001,
                    name="tests",
                    head_sha=sha,
                    event="push",
                    status="completed",
                    conclusion="failure",
                    html_url="https://github.com/acme/stats/actions/runs/1001",
                    run_attempt=1,
                    head_branch="main",
                    workflow_id=7,
                )
            },
            jobs={1001: [WorkflowJob(id=1, name="pytest", conclusion="failure")]},
            logs={(1001, 1): "FAILED tests/test_stats.py::test_average"},
        )
    )
