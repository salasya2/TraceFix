from pathlib import Path

from tracefix.verification.apply import apply_unified_diff
from tracefix.verification.diff import parse_unified_diff


def test_parse_and_apply(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    diff = """diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -1,1 +1,1 @@
-x = 1
+x = 2
"""
    parsed = parse_unified_diff(diff)
    assert parsed.paths == ["src/a.py"]
    assert parsed.additions == 1 and parsed.deletions == 1
    apply_unified_diff(tmp_path, diff)
    assert (src / "a.py").read_text(encoding="utf-8") == "x = 2\n"


def test_rejects_binary_and_escape():
    parsed = parse_unified_diff("diff --git a/x b/x\nGIT binary patch\n")
    assert parsed.binary_files
    parsed = parse_unified_diff("diff --git a/../x b/../x\n")
    assert "../x" in parsed.paths
