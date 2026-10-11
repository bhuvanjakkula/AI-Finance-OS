import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_intelligence_suite_endpoints(monkeypatch):
    monkeypatch.setenv('FINANCE_LOCAL_OWNER_ACCESS', 'true')
    monkeypatch.setenv('FINANCE_LOCAL_OWNER_EMAIL', 'owner-test@example.com')
    monkeypatch.setenv('FINANCE_LOCAL_OWNER_ORG', 'intelligence-test-org')

    with TestClient(app, client=('127.0.0.1', 45000)) as c:
        # Auth
        auth_resp = c.post('/auth/local-owner', headers={'Origin': 'http://127.0.0.1:5173'})
        assert auth_resp.status_code == 200
        token = auth_resp.json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        # Seed workspace
        seed_resp = c.post('/demo/seed', headers=headers)
        assert seed_resp.status_code == 200
        entity_id = seed_resp.json()['entity_id']

        # 1. Analytics Charts
        charts_resp = c.get(f'/analytics/charts?entity_id={entity_id}&period=2026-10', headers=headers)
        assert charts_resp.status_code == 200
        charts_data = charts_resp.json()
        assert len(charts_data['runway_weeks']) == 13
        assert 'metrics' in charts_data
        assert charts_data['metrics']['current_cash'] > 0

        # 2. Copilot What-If Simulator
        sim_payload = {
            'entity_id': entity_id,
            'revenue_delta_percent': -20.0,
            'expense_delta_percent': 10.0,
            'collection_delay_days': 21,
            'capex_or_hire_amount': 5000.0,
            'prompt': 'Recession shock'
        }
        sim_resp = c.post('/copilot/simulate', json=sim_payload, headers=headers)
        assert sim_resp.status_code == 200
        sim_data = sim_resp.json()
        assert sim_data['status'] == 'success'
        assert 'simulated_runway_weeks' in sim_data['results']
        assert len(sim_data['recommendations']) > 0

        # 3. Anomaly Radar & Benford
        anom_resp = c.get(f'/integrity/anomalies?entity_id={entity_id}', headers=headers)
        assert anom_resp.status_code == 200
        anom_data = anom_resp.json()
        assert 'benford_conformity_score' in anom_data
        assert len(anom_data['benford_distribution']) == 9

        # 4. Executive Board Deck
        deck_resp = c.get(f'/executive/deck?entity_id={entity_id}&period=2026-10', headers=headers)
        assert deck_resp.status_code == 200
        deck_data = deck_resp.json()
        assert len(deck_data['slides']) == 3
        assert 'kpi_summary' in deck_data
