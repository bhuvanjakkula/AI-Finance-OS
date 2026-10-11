from test_platform import workspace, member


def test_cash_review_exact_errors_missing_weeks_and_scope(workspace):
    c, h, e, _, slug = workspace
    c.post('/cash/payments', headers=h, json={'entity_id': e, 'reference': 'AR', 'due_date': '2026-09-01', 'amount': '100.00', 'direction': 'inflow'})
    run = c.post('/cash/forecast', headers=h, json={'entity_id': e, 'start_date': '2026-09-01', 'opening_cash': '0'}).json()['id']
    c.post('/bank/import', headers=h, json={'entity_id': e, 'transactions': [
        {'external_id': 'B1', 'date': '2026-09-01', 'amount': '80.01', 'currency': 'USD', 'reference': 'AR'},
        {'external_id': 'B2', 'date': '2026-09-07', 'amount': '-10.02', 'currency': 'USD', 'reference': 'fee'},
        {'external_id': 'B3', 'date': '2026-09-15', 'amount': '500', 'currency': 'USD', 'reference': 'later'},
    ]})
    url = '/cash/forecasts/' + run + '/review'
    params = {'as_of': '2026-09-14', 'tolerance': '20'}
    result = c.get(url, headers=h, params=params)
    assert result.status_code == 200, result.text
    data = result.json()
    assert len(data['weeks']) == 2
    assert data['weeks'][0]['imported_net'] == '69.99'
    assert data['weeks'][0]['net_error'] == '-30.01'
    assert data['weeks'][0]['status'] == 'review'
    assert data['weeks'][1]['status'] == 'no_bank_records'
    assert data['mean_absolute_net_error'] == '30.01'
    assert data['observed_weeks'] == 1
    auditor, _ = member(c, h, slug, 'auditor')
    assert c.get(url, headers=auditor, params=params).status_code == 200
    assert c.get(url, params=params).status_code == 401
    assert c.get(url, headers=h, params={**params, 'tolerance': '-1'}).status_code == 422
    assert c.get(url, headers=h, params={**params, 'as_of': '2099-01-01'}).status_code == 422
    other = c.post('/auth/register', json={'organization': 'Other', 'slug': slug+'other', 'name': 'Other', 'email': 'other@example.test', 'password': 'Other-password-123'}).json()
    assert c.get(url, headers={'Authorization': 'Bearer '+other['token']}, params=params).status_code == 404
    assert c.get(url, headers=h, params={**params, 'as_of': '2026-09-06'}).json()['weeks'] == []
