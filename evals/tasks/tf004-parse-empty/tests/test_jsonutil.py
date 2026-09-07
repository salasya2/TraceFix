from src.jsonutil import load_object


def test_empty():
    assert load_object("") == {}


def test_object():
    assert load_object('{"a": 1}') == {"a": 1}
