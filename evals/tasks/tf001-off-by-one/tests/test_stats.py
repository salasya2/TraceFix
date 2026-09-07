from src.stats import average


def test_average():
    assert average([2, 4]) == 3


def test_average_single():
    assert average([4]) == 4
