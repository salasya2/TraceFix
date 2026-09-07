from datetime import datetime, timezone

from src.when import isoformat


def test_iso():
    dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert isoformat(dt) == "2026-01-02T03:04:05+00:00"
