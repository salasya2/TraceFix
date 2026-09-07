from src.names import display_name


def test_none():
    assert display_name(None) == ""


def test_name():
    assert display_name({"name": "ada"}) == "ADA"
