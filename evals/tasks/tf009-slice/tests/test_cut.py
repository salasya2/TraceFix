from src.cut import rest


def test_rest():
    assert rest("abcd") == "bcd"
