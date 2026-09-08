from src.order import by_age


def test_sort():
    people = [{"name": "a", "age": 2}, {"name": "b", "age": 1}]
    assert [p["age"] for p in by_age(people)] == [1, 2]
