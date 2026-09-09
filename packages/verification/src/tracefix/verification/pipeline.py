from __future__ import annotations

import hashlib
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tracefix.policy.patch_policy import PatchDecision, validate_patch_text
from tracefix.policy.schema import RepositoryPolicy
from tracefix.verification.apply import PatchApplyError, apply_unified_diff, diff_applies_cleanly
from tracefix.verification.diff import parse_unified_diff
from tracefix.verification.harness import HarnessResult, run_pytest
from tracefix.verification.junit import compare_inventories

TestRunner = Callable[..., Awaitable[HarnessResult] | HarnessResult]


@dataclass
class VerificationOutcome:
    verified: bool
    badge: str  # full | partial | none
    target_passed: bool
    flaky: bool
    errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    baseline: HarnessResult | None = None
    candidate: HarnessResult | None = None
    patch_decision: PatchDecision | None = None
    patch_digest: str = ""
    tree_digest: str = ""
    target_ids: list[str] = field(default_factory=list)


def hash_source_tree(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".pytest_cache") or rel in {"junit.xml", ".tracefix-pytest.ini"}:
            continue
        h.update(rel.encode())
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


def _hash_tree(root: Path) -> str:
    return hash_source_tree(root)


def supervisor_errors(result: HarnessResult, *, role: str) -> list[str]:
    errors: list[str] = []
    if result.timed_out:
        errors.append(f"{role} timed out")
    if result.junit_digest is None:
        errors.append(f"{role} missing junit report")
    if result.inventory.errors:
        errors.extend(f"{role}: {item}" for item in result.inventory.errors)
    if result.inventory.collected == 0 and not result.inventory.errors:
        errors.append(f"{role} produced an empty test inventory")
    if role == "candidate" and result.exit_code != 0:
        errors.append(f"candidate process exit {result.exit_code}")
    if role == "baseline" and result.exit_code not in {0, 1}:
        errors.append(f"baseline process exit {result.exit_code}")
    return errors


async def _call_runner(run_tests: TestRunner | None, workdir: Path, **kwargs: Any) -> HarnessResult:
    if run_tests is None:
        return run_pytest(workdir, **kwargs)
    result = run_tests(workdir, **kwargs)
    if hasattr(result, "__await__"):
        return await result  # type: ignore[misc]
    return result  # type: ignore[return-value]


def verify_candidate(
    snapshot: Path,
    diff_text: str,
    policy: RepositoryPolicy,
    *,
    work_root: Path,
    timeout_seconds: int = 120,
    python_bin: str | None = None,
    target_nodeids: list[str] | None = None,
    run_tests: TestRunner | None = None,
) -> VerificationOutcome:
    """Synchronous verifier used by unit tests and the eval runner."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            averify_candidate(
                snapshot,
                diff_text,
                policy,
                work_root=work_root,
                timeout_seconds=timeout_seconds,
                python_bin=python_bin,
                target_nodeids=target_nodeids,
                run_tests=run_tests,
            )
        )
    raise RuntimeError("verify_candidate() cannot be used from a running event loop; await averify_candidate()")


async def averify_candidate(
    snapshot: Path,
    diff_text: str,
    policy: RepositoryPolicy,
    *,
    work_root: Path,
    timeout_seconds: int = 120,
    python_bin: str | None = None,
    target_nodeids: list[str] | None = None,
    run_tests: TestRunner | None = None,
) -> VerificationOutcome:
    parsed = parse_unified_diff(diff_text)
    applies = diff_applies_cleanly(snapshot, parsed)
    decision = validate_patch_text(
        diff_text,
        policy,
        parsed_files=parsed.paths,
        additions=parsed.additions,
        deletions=parsed.deletions,
        binary_files=parsed.binary_files,
        symlink_files=parsed.symlink_files,
        mode_changes=parsed.mode_changes,
        applies_cleanly=applies,
    )
    patch_digest = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    if not decision.accepted:
        return VerificationOutcome(
            False,
            "none",
            False,
            False,
            errors=decision.errors,
            patch_decision=decision,
            patch_digest=patch_digest,
        )

    baseline_dir = work_root / "baseline"
    candidate_dir = work_root / "candidate"
    if baseline_dir.exists():
        shutil.rmtree(baseline_dir)
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    shutil.copytree(snapshot, baseline_dir)
    shutil.copytree(snapshot, candidate_dir)

    first = await _call_runner(
        run_tests, baseline_dir, timeout_seconds=timeout_seconds, python_bin=python_bin
    )
    second = await _call_runner(
        run_tests, baseline_dir, timeout_seconds=timeout_seconds, python_bin=python_bin
    )
    baseline_errors = supervisor_errors(first, role="baseline") + supervisor_errors(second, role="baseline")
    if baseline_errors:
        return VerificationOutcome(
            False,
            "none",
            False,
            first.timed_out or second.timed_out,
            errors=baseline_errors,
            limitations=["baseline supervisor rejected the process"],
            baseline=second,
            patch_decision=decision,
            patch_digest=patch_digest,
        )
    if first.inventory.signature() != second.inventory.signature():
        return VerificationOutcome(
            False,
            "none",
            False,
            True,
            errors=["baseline failure signature was not stable"],
            limitations=["two-run flake screen is a heuristic, not proof of determinism"],
            baseline=second,
            patch_decision=decision,
            patch_digest=patch_digest,
        )
    if not first.inventory.failed_ids:
        return VerificationOutcome(
            False,
            "none",
            False,
            False,
            errors=["baseline did not reproduce a failing test"],
            baseline=first,
            patch_decision=decision,
            patch_digest=patch_digest,
        )

    targets = set(target_nodeids or first.inventory.failed_ids)
    try:
        apply_unified_diff(candidate_dir, diff_text)
    except PatchApplyError as exc:
        return VerificationOutcome(
            False,
            "none",
            False,
            False,
            errors=[str(exc)],
            baseline=first,
            patch_decision=decision,
            patch_digest=patch_digest,
        )

    cand = await _call_runner(
        run_tests, candidate_dir, timeout_seconds=timeout_seconds, python_bin=python_bin
    )
    inventory_errors = compare_inventories(first.inventory, cand.inventory)
    still_failing = targets & cand.inventory.failed_ids
    target_passed = not still_failing and bool(targets)
    errors = list(inventory_errors)
    errors.extend(supervisor_errors(cand, role="candidate"))
    if still_failing:
        errors.append(f"target still failing: {sorted(still_failing)}")
    if cand.inventory.errors:
        errors.extend(cand.inventory.errors)
    existing_failures = first.inventory.failed_ids - targets
    remaining_existing = existing_failures & cand.inventory.failed_ids
    unexplained_cleared = existing_failures - cand.inventory.failed_ids - cand.inventory.ids
    if unexplained_cleared:
        errors.append(f"unexplained test disappearance: {sorted(unexplained_cleared)}")

    verified = target_passed and not errors
    full_suite_clean = verified and not cand.inventory.failed_ids and not remaining_existing
    badge = "none"
    limitations = [
        "Candidate code can interfere with a Python test process; green tests do not prove harmlessness.",
        "Human review remains required before publication.",
    ]
    if verified and full_suite_clean:
        badge = "full"
    elif verified:
        badge = "partial"
        limitations.append("baseline suite had existing failures; full-verification badge withheld")
    tree_digest = hash_source_tree(candidate_dir)
    return VerificationOutcome(
        verified=verified,
        badge=badge,
        target_passed=target_passed,
        flaky=False,
        errors=errors,
        limitations=limitations,
        baseline=first,
        candidate=cand,
        patch_decision=decision,
        patch_digest=patch_digest,
        tree_digest=tree_digest,
        target_ids=sorted(targets),
    )
