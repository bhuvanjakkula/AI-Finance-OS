from test_platform import workspace, member


def test_reverse_limit_boundary_and_baseline_failure(workspace):
    c,h,e,_,slug=workspace
    for ref,value,direction in [('AR','100','inflow'),('AP','80','outflow')]:
        c.post('/cash/payments',headers=h,json={'entity_id':e,'reference':ref,'due_date':'2026-09-01','amount':value,'direction':direction})
    forecast=c.post('/cash/forecast',headers=h,json={'entity_id':e,'start_date':'2026-09-01','opening_cash':'50'}).json()['id']
    body={'forecast_id':forecast,'reserve':'40'}
    r=c.post('/cash/liquidity-limits',headers=h,json=body)
    assert r.status_code==201,r.text
    data=r.json()
    assert data['maximum_collection_loss_percent']=='30.00'
    assert data['minimum_cash_at_limit']=='40.00'
    assert data['first_breach_at_next_step']=='2026-09-07'
    assert data['funding_with_no_collections']=='70.00'
    assert all(float(w['headroom'])>=0 for w in data['weeks'])
    saved=next(run for run in c.get('/runs',headers=h).json() if run['id']==data['id'])
    assert saved['output']['source_forecast_id']==forecast
    failed=c.post('/cash/liquidity-limits',headers=h,json={**body,'reserve':'60'}).json()
    assert failed['status']=='baseline_breaches_reserve'
    assert failed['maximum_collection_loss_percent'] is None
    assert failed['baseline_first_breach']=='opening'
    assert failed['baseline_funding_to_reserve']=='10.00'
    assert c.post('/cash/liquidity-limits',headers=h,json={**body,'reserve':'-1'}).status_code==422
    assert c.post('/cash/liquidity-limits',headers=h,json={**body,'forecast_id':'foreign'}).status_code==404
    assert c.post('/cash/liquidity-limits',headers=h,json={**body,'forecast_id':data['id']}).status_code==422
    auditor,_=member(c,h,slug,'auditor')
    assert c.post('/cash/liquidity-limits',headers=auditor,json=body).status_code==403
    assert c.post('/cash/liquidity-limits',json=body).status_code==401


def test_reverse_limit_survives_without_collections(workspace):
    c,h,e,_,_=workspace
    forecast=c.post('/cash/forecast',headers=h,json={'entity_id':e,'start_date':'2026-09-01','opening_cash':'100'}).json()['id']
    data=c.post('/cash/liquidity-limits',headers=h,json={'forecast_id':forecast,'reserve':'100'}).json()
    assert data['status']=='all_collections_can_be_lost'
    assert data['maximum_collection_loss_percent']=='100.00'
    assert data['first_breach_at_next_step'] is None
    assert data['funding_with_no_collections']=='0.00'
