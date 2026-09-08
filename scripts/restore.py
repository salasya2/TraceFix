"""Restore a backup produced by scripts/backup.py into a clean .data directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def restore(src: Path, dest: Path | None = None) -> Path:
    dest = dest or (ROOT / ".data")
    dest.mkdir(parents=True, exist_ok=True)
    db = src / "tracefix.db"
    if db.exists():
        shutil.copy2(db, dest / "tracefix.db")
    arts = src / "artifacts"
    if arts.exists():
        target = dest / "artifacts"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(arts, target)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="src", required=True)
    args = parser.parse_args()
    print(restore(Path(args.src)))


if __name__ == "__main__":
    main()
