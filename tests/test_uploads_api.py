import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

def test_uploads_requires_tenant():
    r = client.get("/uploads")
    assert r.status_code == 401

# Note: Additional tests require a running DB or mocking db.connections
