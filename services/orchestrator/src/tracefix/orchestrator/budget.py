from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class Lease:
    id: UUID
    tenant_id: UUID
    run_id: UUID
    reserved: float
    settled: float = 0.0
    status: str = "reserved"


class BudgetBook:
    def __init__(self, tenant_limit: float = 50.0) -> None:
        self.tenant_limit = tenant_limit
        self.leases: dict[UUID, Lease] = {}
        self.tenant_reserved: dict[UUID, float] = {}

    def remaining(self, tenant_id: UUID) -> float:
        return self.tenant_limit - self.tenant_reserved.get(tenant_id, 0.0)

    def reserve(self, tenant_id: UUID, run_id: UUID, amount: float) -> Lease:
        used = self.tenant_reserved.get(tenant_id, 0.0)
        if used + amount > self.tenant_limit:
            raise RuntimeError("BUDGET_EXCEEDED")
        self.tenant_reserved[tenant_id] = used + amount
        lease = Lease(id=uuid4(), tenant_id=tenant_id, run_id=run_id, reserved=amount)
        self.leases[lease.id] = lease
        return lease

    def settle(self, lease_id: UUID, actual: float) -> None:
        lease = self.leases[lease_id]
        if lease.status != "reserved":
            return
        actual = min(actual, lease.reserved)
        unused = lease.reserved - actual
        self.tenant_reserved[lease.tenant_id] = max(
            0.0, self.tenant_reserved.get(lease.tenant_id, 0.0) - unused
        )
        lease.settled = actual
        lease.status = "settled"
