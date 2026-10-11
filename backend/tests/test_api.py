import os
import tempfile

from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app import database
from app.legacy_main import app
from app.database import Base
from app.models import LedgerLine, ExceptionRecord, AuditEvent

def test_demo_flow():
    with TestClient(app) as client:
        response = client.post('/demo/seed', headers={'X-Tenant-ID':'testone'})
        assert response.status_code == 200
        assert response.json()['imported'] == 6
        assert client.post('/demo/seed', headers={'X-Tenant-ID':'testone'}).json()['imported'] == 0
        summary = client.get('/dashboard', headers={'X-Tenant-ID':'testone'}).json()
        assert summary['lines'] == 6
        assert summary['open_exceptions'] == 2
        report = client.get('/reports/trial-balance', headers={'X-Tenant-ID':'testone'}).json()
        assert len(report['rows']) == 4
        assert client.get('/dashboard', headers={'X-Tenant-ID':'testtwo'}).json()['lines'] == 0
        exc = client.get('/exceptions', headers={'X-Tenant-ID':'testone'}).json()[0]
        assert client.get(f"/exceptions/{exc['id']}/investigate", headers={'X-Tenant-ID':'testone'}).json()['method'] == 'deterministic_rules_not_ai'
