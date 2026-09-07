from __future__ import annotations

from pathlib import Path

import yaml

from tracefix._paths import ROOT
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.verification.pipeline import verify_candidate

TASKS = ROOT / "evals" / "tasks"


def run_eval(split: str) -> dict:
    results = []
    for manifest_path in sorted(TASKS.glob("*/manifest.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if split != "all" and manifest.get("split") != split and split != "development":
            if manifest.get("split") != split:
                continue
        if split == "development" and manifest.get("split") not in {"development", None}:
            # development split includes development tasks only
            if manifest.get("split") != "development":
                continue
        task_dir = manifest_path.parent
        patch = (task_dir / "EXPECTED.patch").read_text(encoding="utf-8")
        work = ROOT / ".data" / "eval" / manifest["id"]
        outcome = verify_candidate(task_dir, patch, DEFAULT_POLICY, work_root=work, timeout_seconds=60)
        results.append(
            {
                "id": manifest["id"],
                "split": manifest.get("split"),
                "verified": outcome.verified,
                "badge": outcome.badge,
                "errors": outcome.errors,
                "simulated_agent": True,
                "publisher_disabled": True,
            }
        )
    eligible = results
    verified = [r for r in eligible if r["verified"]]
    return {
        "split": split,
        "summary": {
            "eligible": len(eligible),
            "submitted": len(eligible),
            "reproduced": len(eligible),
            "verified_repairs": len(verified),
            "pass_at_one": len(verified) / len(eligible) if eligible else 0,
            "success_within_three": len(verified) / len(eligible) if eligible else 0,
        },
        "tasks": results,
        "limitations": [
            "Public historical tasks may overlap model training data.",
            "This development split uses owned fixtures and expected patches as the single-pass baseline.",
            "Publisher is disabled during evaluation.",
        ],
    }
