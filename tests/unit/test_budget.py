from uuid import uuid4

from tracefix.orchestrator.budget import BudgetBook


def test_concurrent_reservations_cannot_overspend():
    book = BudgetBook(tenant_limit=2.0)
    tenant = uuid4()
    book.reserve(tenant, uuid4(), 1.5)
    try:
        book.reserve(tenant, uuid4(), 1.0)
        assert False, "should not overspend"
    except RuntimeError as exc:
        assert "BUDGET" in str(exc)
