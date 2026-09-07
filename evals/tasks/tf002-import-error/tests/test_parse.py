from src.parse import parse_int


def test_parse_int():
    assert parse_int("3") == 3
