from tracefix.storage.engine import _apply_rls


def test_rls_policy_sql_uses_and_with_check():
    executed: list[str] = []

    class Fake:
        def exec_driver_sql(self, sql: str) -> None:
            executed.append(" ".join(sql.split()))

    _apply_rls(Fake())
    joined = "\n".join(executed)
    assert "ENABLE ROW LEVEL SECURITY" in joined
    assert "USING (tenant_id = current_setting('tracefix.tenant_id')::uuid)" in joined
    assert "WITH CHECK (tenant_id = current_setting('tracefix.tenant_id')::uuid)" in joined
