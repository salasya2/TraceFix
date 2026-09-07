from src.httputil import status_for


def test_error_is_500():
    assert status_for(True) == 500


def test_ok():
    assert status_for(False) == 200
