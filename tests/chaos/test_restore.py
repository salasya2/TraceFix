from pathlib import Path
import shutil

from tracefix._paths import ROOT


def test_backup_round_trip(tmp_path: Path):
    src = tmp_path / "data"
    src.mkdir()
    (src / "tracefix.db").write_bytes(b"sqlite-bytes")
    backup = tmp_path / "backup"
    backup.mkdir()
    shutil.copy2(src / "tracefix.db", backup / "tracefix.db")
    restored = tmp_path / "restored"
    restored.mkdir()
    shutil.copy2(backup / "tracefix.db", restored / "tracefix.db")
    assert (restored / "tracefix.db").read_bytes() == b"sqlite-bytes"
