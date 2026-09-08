import pytest

from tracefix.executor.adapters.gvisor import GVisorAdapter, SandboxRuntimeUnavailable
from tracefix.executor.broker import JobSpec
from pathlib import Path


@pytest.mark.asyncio
async def test_missing_runtime_fails_closed(tmp_path: Path):
    adapter = GVisorAdapter(runtime_available=False)
    spec = JobSpec(
        tenant_id="t",
        run_id="r",
        capability="cap",
        source_digest="x",
        image_digest="x",
        dependency_bundle_digest="x",
        profile_id="python312-pytest-v1",
        stage="verify",
        snapshot=tmp_path,
    )
    with pytest.raises(SandboxRuntimeUnavailable):
        await adapter.run_tests(spec)
