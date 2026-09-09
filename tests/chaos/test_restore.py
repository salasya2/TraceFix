import importlib.util
from pathlib import Path

from tracefix._paths import ROOT


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_backup_round_trip(tmp_path: Path, monkeypatch):
    backup_mod = _load("tf_backup", ROOT / "scripts" / "backup.py")
    restore_mod = _load("tf_restore", ROOT / "scripts" / "restore.py")
    monkeypatch.setattr(backup_mod, "ROOT", tmp_path)
    monkeypatch.setattr(restore_mod, "ROOT", tmp_path)
    data = tmp_path / ".data"
    data.mkdir()
    (data / "tracefix.db").write_bytes(b"sqlite-bytes")
    arts = data / "artifacts"
    arts.mkdir()
    (arts / "blob").write_text("ok", encoding="utf-8")
    dest = backup_mod.backup(tmp_path / "backup")
    assert (dest / "tracefix.db").read_bytes() == b"sqlite-bytes"
    restored = restore_mod.restore(dest, tmp_path / "restored")
    assert (restored / "tracefix.db").read_bytes() == b"sqlite-bytes"
    assert (restored / "artifacts" / "blob").read_text(encoding="utf-8") == "ok"
