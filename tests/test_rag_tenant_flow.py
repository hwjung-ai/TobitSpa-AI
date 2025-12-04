import pytest


def test_rag_service_tenant_filter(monkeypatch):
    import services.rag_service as rs

    class DummyCursor:
        last_sql = None
        def execute(self, sql, params):
            DummyCursor.last_sql = sql
        def fetchall(self):
            return [
                {
                    "title": "Doc1",
                    "converted_pdf": "/path/doc1.pdf",
                    "page_num": 1,
                    "source_path": "/path/doc1",
                    "content": "dummy content for testing",
                    "score": 0.9,
                }
            ]
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class DummyConn:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass
        def cursor(self, cursor_factory=None):
            return DummyCursor()

    monkeypatch.setattr(rs, "get_pg_conn", lambda: DummyConn())
    monkeypatch.setattr(rs, "compute_embedding", lambda text: [0.1, 0.2, 0.3])

    res = rs.perform_rag_search("test query", tenant_id="tenantA")
    assert isinstance(res, dict)
    assert "sources" in res
    assert isinstance(res["sources"], list)

    # verify that the SQL included tenant condition
    assert DummyCursor.last_sql is not None
    assert "tenant_id" in DummyCursor.last_sql
