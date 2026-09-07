from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from tracefix.storage.models import Artifact


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        *,
        tenant_id: UUID,
        kind: str,
        data: bytes,
        access_class: str = "redacted",
        run_id: UUID | None = None,
    ) -> Artifact:
        digest = hashlib.sha256(data).hexdigest()
        key = f"{tenant_id}/{kind}/{digest}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return Artifact(
            id=uuid4(),
            tenant_id=tenant_id,
            kind=kind,
            storage_key=key,
            sha256=digest,
            size=len(data),
            access_class=access_class,
            run_id=run_id,
        )

    def get(self, storage_key: str) -> bytes:
        path = self.root / storage_key
        if not path.exists():
            raise FileNotFoundError(storage_key)
        return path.read_bytes()
