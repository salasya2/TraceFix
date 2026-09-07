from src.merge import merge


def test_does_not_mutate():
    base = {"a": 1}
    out = merge(base, {"b": 2})
    assert out == {"a": 1, "b": 2}
    assert base == {"a": 1}
