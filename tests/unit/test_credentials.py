from uuid import uuid4

from tracefix.credential_broker.broker import CredentialBroker, TokenRequest
from tracefix.domain.roles import ServiceIdentity


def test_fetcher_cannot_mint_write_and_no_cross_tenant():
    broker = CredentialBroker(fixture_mode=True)
    tenant = uuid4()
    other = uuid4()
    repo = uuid4()
    broker.register_repo(tenant, repo, 9)
    req = TokenRequest(ServiceIdentity.FETCHER, tenant, repo, 9, "write")
    try:
        broker.mint(req)
        assert False
    except PermissionError:
        pass
    read = broker.mint(TokenRequest(ServiceIdentity.FETCHER, tenant, repo, 9, "read"))
    assert "contents:read" in read.permissions
    try:
        broker.mint(TokenRequest(ServiceIdentity.PUBLISHER, other, repo, 9, "write", "op-1"))
        assert False
    except PermissionError:
        pass
    broker.approve_publication("op-1")
    write = broker.mint(TokenRequest(ServiceIdentity.PUBLISHER, tenant, repo, 9, "write", "op-1"))
    assert "pull_requests:write" in write.permissions
