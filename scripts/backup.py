"""Copy SQLite DB and local artifacts to a timestamped backup directory."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def backup(dest: Path | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest or (ROOT / "artifacts" / "backups" / stamp)
    dest.mkdir(parents=True, exist_ok=True)
    db = ROOT / ".data" / "tracefix.db"
    if db.exists():
        shutil.copy2(db, dest / "tracefix.db")
    arts = ROOT / ".data" / "artifacts"
    if arts.exists():
        shutil.copytree(arts, dest / "artifacts", dirs_exist_ok=True)
    (dest / "README.txt").write_text(
        "TraceFix backup. Restore with python scripts/restore.py --from " + str(dest),
        encoding="utf-8",
    )
    return dest


if __name__ == "__main__":
    print(backup())
