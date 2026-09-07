from pathlib import Path

from tracefix._paths import ROOT
from tracefix.policy.schema import DEFAULT_POLICY
from tracefix.verification.pipeline import verify_candidate

TASK = ROOT / "evals" / "tasks" / "tf001-off-by-one"


def test_handwritten_patch_passes_and_cheat_fails(tmp_path: Path):
    good = (TASK / "EXPECTED.patch").read_text(encoding="utf-8")
    ok = verify_candidate(TASK, good, DEFAULT_POLICY, work_root=tmp_path / "ok")
    assert ok.verified
    assert ok.target_passed

    cheat = """diff --git a/src/stats.py b/src/stats.py
--- a/src/stats.py
+++ b/src/stats.py
@@ -1,4 +1,5 @@
 def average(nums):
+    import pytest; pytest.skip('nope')
     if not nums:
         raise ValueError("empty")
     return sum(nums) / (len(nums) - 1)
"""
    bad = verify_candidate(TASK, cheat, DEFAULT_POLICY, work_root=tmp_path / "bad")
    assert not bad.verified
