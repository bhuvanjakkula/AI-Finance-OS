from test_platform import workspace, member

def test_briefing_scope_and_missing_scenarios(workspace):
    c,h,e,_,slug=workspace
    r=c.get('/executive/briefing',headers=h,params={'period':'2026-10'})
    assert r.status_code==200,r.text
    row=r.json()['entities'][0]
    assert row['entity_id']==e and row['currency']=='USD'
    assert row['stress_run_id'] is None and row['largest_stress_funding_gap'] is None
    assert row['limit_status']=='not_tested'
    assert row['attention'] and r.json()['entities_needing_review']==1
    forecast=c.post('/cash/forecast',headers=h,json={'entity_id':e,'start_date':'2026-10-01','opening_cash':'50'}).json()['id']
    stress=c.post('/cash/stress',headers=h,json={'forecast_id':forecast,'reserve':'100'}).json()
    limit=c.post('/cash/liquidity-limits',headers=h,json={'forecast_id':forecast,'reserve':'100'}).json()
    row=c.get('/executive/briefing',headers=h,params={'period':'2026-10'}).json()['entities'][0]
    assert row['stress_run_id']==stress['id'] and row['limit_run_id']==limit['id']
    assert row['largest_stress_funding_gap']=='50.00'
    auditor,_=member(c,h,slug,'auditor')
    assert c.get('/executive/briefing',headers=auditor,params={'period':'2026-10'}).status_code==200
    assert c.get('/executive/briefing',params={'period':'2026-10'}).status_code==401
    assert c.get('/executive/briefing',headers=h,params={'period':'invalid'}).status_code==422
