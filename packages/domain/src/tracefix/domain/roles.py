from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MAINTAINER = "maintainer"
    VIEWER = "viewer"


class ServiceIdentity(StrEnum):
    API = "api"
    ORCHESTRATOR = "orchestrator"
    FETCHER = "fetcher"
    EXECUTOR = "executor"
    PUBLISHER = "publisher"
    CREDENTIAL_BROKER = "credential_broker"
    SWEEPER = "sweeper"


READ_ROLES = frozenset({Role.OWNER, Role.ADMIN, Role.MAINTAINER, Role.VIEWER})
MAINTAINER_ROLES = frozenset({Role.OWNER, Role.ADMIN, Role.MAINTAINER})
ADMIN_ROLES = frozenset({Role.OWNER, Role.ADMIN})
APPROVER_ROLES = MAINTAINER_ROLES
