from __future__ import annotations

from dataclasses import dataclass

from tracefix.domain.reasons import ReasonCode
from tracefix.policy.schema import RepositoryPolicy


@dataclass(frozen=True)
class AdmissionContext:
    event_type: str
    is_fork: bool
    workflow_id: int | None
    conclusion: str | None
    head_sha: str | None
    execution_sha: str | None
    checkout_trusted: bool
    language_profile_ok: bool
    bot_generated: bool
    installation_selected: bool
    tenant_suspended: bool
    emergency_stop: bool


@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    reason: ReasonCode
    detail: str


def admit_event(policy: RepositoryPolicy, ctx: AdmissionContext) -> AdmissionResult:
    if ctx.emergency_stop:
        return AdmissionResult(False, ReasonCode.TENANT_SUSPENDED, "executor emergency stop is engaged")
    if ctx.tenant_suspended:
        return AdmissionResult(False, ReasonCode.TENANT_SUSPENDED, "tenant is suspended")
    if not ctx.installation_selected:
        return AdmissionResult(False, ReasonCode.EVENT_IGNORED, "repository is not selected")
    if policy.mode == "disabled":
        return AdmissionResult(False, ReasonCode.POLICY_DENIED, "repository policy is disabled")
    if ctx.bot_generated:
        return AdmissionResult(False, ReasonCode.EVENT_IGNORED, "ignoring TraceFix bot branches")
    if ctx.event_type not in policy.eligible_events:
        return AdmissionResult(False, ReasonCode.EVENT_IGNORED, f"event {ctx.event_type} is not eligible")
    if ctx.is_fork and not policy.allow_forks:
        return AdmissionResult(False, ReasonCode.FORK_PR_UNSUPPORTED, "fork pull requests are out of scope")
    if ctx.conclusion not in {"failure", "timed_out", "cancelled"} and ctx.conclusion is not None:
        if ctx.conclusion == "success":
            return AdmissionResult(False, ReasonCode.EVENT_IGNORED, "run succeeded")
    if policy.workflow_ids and ctx.workflow_id is not None and ctx.workflow_id not in policy.workflow_ids:
        return AdmissionResult(False, ReasonCode.EVENT_IGNORED, "workflow is not in the allowlist")
    if not ctx.language_profile_ok:
        return AdmissionResult(False, ReasonCode.UNSUPPORTED_PROFILE, "execution profile is not supported")
    if not ctx.checkout_trusted or not ctx.execution_sha:
        return AdmissionResult(False, ReasonCode.UNSUPPORTED_CHECKOUT, "cannot establish exact execution revision")
    return AdmissionResult(True, ReasonCode.ADMITTED, "eligible")
