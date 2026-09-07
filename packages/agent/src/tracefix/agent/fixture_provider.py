from __future__ import annotations

from pathlib import Path

from tracefix.agent.providers import ProviderResult
from tracefix.verification.diff import parse_unified_diff


class FixtureProvider:
    """Labeled simulated agent. Uses the real tool router; does not skip verification."""

    name = "fixture"
    simulated = True

    def __init__(self, snapshot: Path, traceback: str = "") -> None:
        self.snapshot = snapshot
        self.traceback = traceback
        self._step = 0
        self._patch: str | None = None

    def load_expected_patch(self) -> str:
        patch_path = self.snapshot / "EXPECTED.patch"
        if patch_path.exists():
            return patch_path.read_text(encoding="utf-8")
        return self._infer_patch()

    def _infer_patch(self) -> str:
        # Minimal owned-task heuristic: fix `len(nums) - 1` average bug if present.
        for path in self.snapshot.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "len(nums) - 1" in text:
                rel = path.relative_to(self.snapshot).as_posix()
                return (
                    f"diff --git a/{rel} b/{rel}\n"
                    f"--- a/{rel}\n"
                    f"+++ b/{rel}\n"
                    "@@ -1,8 +1,8 @@\n"
                    " def average(nums):\n"
                    "     if not nums:\n"
                    "         raise ValueError('empty')\n"
                    "-    return sum(nums) / (len(nums) - 1)\n"
                    "+    return sum(nums) / len(nums)\n"
                )
        raise FileNotFoundError("no expected patch for fixture")

    async def complete(self, *, system: str, user: str, tools: list, model: str) -> ProviderResult:
        self._step += 1
        if self._step == 1:
            target = "src/stats.py"
            src = self.snapshot / target
            if not src.exists():
                py_files = [p.relative_to(self.snapshot).as_posix() for p in self.snapshot.rglob("*.py") if "test" not in p.as_posix()]
                target = py_files[0] if py_files else "src/stats.py"
            return ProviderResult(
                text="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "arguments": {
                            "snapshot_id": "current",
                            "relative_path": target,
                            "start_line": 1,
                            "end_line": 80,
                        },
                    }
                ],
                input_tokens=200,
                output_tokens=40,
                model=model,
                provider=self.name,
                simulated=True,
            )
        if self._step == 2:
            patch = self.load_expected_patch()
            self._patch = patch
            parsed = parse_unified_diff(patch)
            path = parsed.paths[0] if parsed.paths else "src/stats.py"
            return ProviderResult(
                text="",
                tool_calls=[
                    {
                        "name": "submit_patch",
                        "arguments": {"snapshot_id": "current", "unified_diff": patch},
                    }
                ],
                input_tokens=240,
                output_tokens=80,
                model=model,
                provider=self.name,
                simulated=True,
            )
        return ProviderResult(
            text=(
                '{"failure_category":"off_by_one","hypothesis":"denominator uses n-1",'
                '"expected_behavior":"average uses len(nums)",'
                '"known_limitations":["fixture agent"],'
                '"proposed_changed_paths":["src/stats.py"],'
                '"evidence":[{"path":"src/stats.py","revision":"fixture","start_line":1,"end_line":8}]}'
            ),
            tool_calls=[],
            input_tokens=80,
            output_tokens=120,
            model=model,
            provider=self.name,
            simulated=True,
        )
