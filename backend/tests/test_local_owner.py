from fastapi.testclient import TestClient
from app.main import app

def test_local_owner_disabled_and_origin_checks(monkeypatch):
    with TestClient(app,client=('127.0.0.1',45000)) as c:
        monkeypatch.setenv('FINANCE_LOCAL_OWNER_ACCESS','false')
        assert c.post('/auth/local-owner').status_code==403
        monkeypatch.setenv('FINANCE_LOCAL_OWNER_ACCESS','true')
        monkeypatch.setenv('FINANCE_LOCAL_OWNER_EMAIL','owner-local@example.test')
        monkeypatch.setenv('FINANCE_LOCAL_OWNER_ORG','local-owner-test')
        assert c.post('/auth/local-owner',headers={'Origin':'https://evil.example'}).status_code==403
        assert c.post('/auth/local-owner',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
        response=c.post('/auth/local-owner',headers={'Origin':'http://127.0.0.1:5174'})
        assert response.status_code==200,response.text
        assert response.json()['user']['role']=='owner'
        monkeypatch.setenv('FINANCE_ENV','production')
        assert c.post('/auth/local-owner').status_code in (400,403)
