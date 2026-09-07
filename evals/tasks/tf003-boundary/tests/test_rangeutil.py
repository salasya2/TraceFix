from src.rangeutil import inclusive_range


def test_inclusive():
    assert inclusive_range(1, 3) == [1, 2, 3]
