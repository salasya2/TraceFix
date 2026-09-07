import io
import zipfile
from pathlib import Path

from tracefix.github.archive import UnsafeArchive, extract_zip_safe


def test_traversal_and_bomb_rejected(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.py", "nope")
    try:
        extract_zip_safe(archive, tmp_path / "out", max_files=10, max_bytes=1000)
        assert False
    except UnsafeArchive:
        pass
    archive2 = tmp_path / "many.zip"
    with zipfile.ZipFile(archive2, "w") as zf:
        for i in range(50):
            zf.writestr(f"f{i}.txt", "x")
    try:
        extract_zip_safe(archive2, tmp_path / "out2", max_files=10, max_bytes=10_000)
        assert False
    except UnsafeArchive:
        pass
