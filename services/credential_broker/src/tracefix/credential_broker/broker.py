from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from tracefix.domain.roles import ServiceIdentity


@dataclass(frozen=True)
class TokenRequest:
    caller: ServiceIdentity
    tenant_id: UUID
    repository_id: UUID
    installation_id: int
    operation: str
    publication_operation_id: str | None = None


@dataclass(frozen=True)
class IssuedToken:
    token: str
    permissions: tuple[str, ...]
    repositories: tuple[str, ...]


class CredentialBroker:
    """Mints repository-scoped tokens. Tokens never leave this boundary into logs or sandboxes."""

    READ = ("actions:read", "contents:read")
    WRITE = ("contents:write", "pull_requests:write")

    def __init__(self, *, app_private_key: str | None = None, fixture_mode: bool = True) -> None:
        self.app_private_key = app_private_key
        self.fixture_mode = fixture_mode
        self._approved_publications: set[str] = set()
        self._known: dict[tuple[UUID, UUID], int] = {}

    def register_repo(self, tenant_id: UUID, repository_id: UUID, installation_id: int) -> None:
        self._known[(tenant_id, repository_id)] = installation_id

    def approve_publication(self, operation_id: str) -> None:
        self._approved_publications.add(operation_id)

    def mint(self, request: TokenRequest) -> IssuedToken:
        expected = self._known.get((request.tenant_id, request.repository_id))
        if expected is None or expected != request.installation_id:
            raise PermissionError("installation/tenant/repository mismatch")
        if request.caller in {ServiceIdentity.FETCHER, ServiceIdentity.ORCHESTRATOR}:
            if request.operation != "read":
                raise PermissionError("fetcher/orchestrator cannot mint write tokens")
            return IssuedToken("fixture-read-token" if self.fixture_mode else "redacted", self.READ, ())
        if request.caller == ServiceIdentity.PUBLISHER:
            if request.operation != "write":
                raise PermissionError("publisher requested an invalid operation")
            if not request.publication_operation_id:
                raise PermissionError("publisher must reference an approved publication operation")
            if request.publication_operation_id not in self._approved_publications:
                raise PermissionError("publication operation is not approved")
            return IssuedToken("fixture-write-token" if self.fixture_mode else "redacted", self.WRITE, ())
        raise PermissionError("caller is not authorized to mint tokens")
