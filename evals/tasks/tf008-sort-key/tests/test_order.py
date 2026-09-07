from src.order import by_age


def test_sort():
    people = [{"name": "b", "age": 2}, {"name": "a", "age": 1}]
    assert by_age(people)[0]["name"] == "a"
    assert [p["age"] for p in by_age(people)] == [1, 2]
