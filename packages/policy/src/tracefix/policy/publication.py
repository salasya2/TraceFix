from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from tracefix.domain.reasons import ReasonCode
from tracefix.policy.schema import RepositoryPolicy


@dataclass(frozen=True)
class PublicationDecision:
    allowed: bool
    mode: str
    reason: ReasonCode
    detail: str


def decide_publication(
    policy: RepositoryPolicy,
    *,
    approved: bool,
    approval_expires_at: datetime | None,
    now: datetime,
    patch_digest: str,
    approved_digest: str | None,
    source_sha: str,
    approved_source_sha: str | None,
    base_sha: str,
    approved_base_sha: str | None,
    policy_version: int,
    approved_policy_version: int | None,
    safety_fingerprint_current: str | None,
    safety_fingerprint_approved: str | None,
    safety_review_ok: bool,
    refs_unchanged: bool,
    installation_active: bool,
) -> PublicationDecision:
    if not installation_active:
        return PublicationDecision(
            False, "blocked", ReasonCode.INSTALLATION_REMOVED, "installation is no longer active"
        )
    if not approved:
        return PublicationDecision(False, "blocked", ReasonCode.POLICY_DENIED, "missing approval")
    if approval_expires_at is not None and approval_expires_at.tzinfo is None:
        approval_expires_at = approval_expires_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if approval_expires_at is None or now >= approval_expires_at:
        return PublicationDecision(False, "blocked", ReasonCode.APPROVAL_EXPIRED, "approval expired")
    if approved_digest != patch_digest:
        return PublicationDecision(
            False, "blocked", ReasonCode.APPROVAL_DIGEST_MISMATCH, "patch digest changed"
        )
    if approved_source_sha != source_sha or approved_base_sha != base_sha:
        return PublicationDecision(False, "blocked", ReasonCode.SOURCE_MOVED, "source or base SHA moved")
    if approved_policy_version != policy_version:
        return PublicationDecision(False, "blocked", ReasonCode.POLICY_DENIED, "policy version changed")
    if not refs_unchanged:
        return PublicationDecision(False, "blocked", ReasonCode.SOURCE_MOVED, "refs advanced since approval")
    if policy.publication.require_workflow_safety_review and not safety_review_ok:
        return PublicationDecision(
            True,
            "patch_download",
            ReasonCode.PATCH_DOWNLOAD_ONLY,
            "workflow safety cannot be established; patch-download mode",
        )
    if (
        policy.publication.require_workflow_safety_review
        and safety_fingerprint_approved
        and safety_fingerprint_current != safety_fingerprint_approved
    ):
        return PublicationDecision(
            False,
            "blocked",
            ReasonCode.SAFETY_FINGERPRINT_CHANGED,
            "workflow safety fingerprint changed",
        )
    if policy.mode == "report_only":
        return PublicationDecision(
            True,
            "patch_download",
            ReasonCode.PATCH_DOWNLOAD_ONLY,
            "report-only policy",
        )
    return PublicationDecision(
        True,
        "draft_pr" if policy.publication.draft_only else "draft_pr",
        ReasonCode.PUBLISHED,
        "eligible for draft publication",
    )
