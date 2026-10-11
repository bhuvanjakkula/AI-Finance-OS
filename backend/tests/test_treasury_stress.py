from test_platform import workspace, member


def test_stress_funding_delay_horizon_and_access(workspace):
    c,h,e,_,slug=workspace
    for ref,due,value,direction in [('AR','2026-09-01','100','inflow'),('AP','2026-09-01','80','outflow'),('LATE','2026-11-24','30','inflow')]:
        assert c.post('/cash/payments',headers=h,json={'entity_id':e,'reference':ref,'due_date':due,'amount':value,'direction':direction}).status_code==201
    forecast=c.post('/cash/forecast',headers=h,json={'entity_id':e,'start_date':'2026-09-01','opening_cash':'50'}).json()['id']
    body={'forecast_id':forecast,'reserve':'40','collection_delay_weeks':2,'inflow_factor':'0.5','outflow_factor':'1.25'}
    response=c.post('/cash/stress',headers=h,json=body)
    assert response.status_code==201,response.text
    rows={s['name']:s for s in response.json()['scenarios']}
    assert rows['Baseline']['minimum_cash']=='50.00'
    assert rows['Baseline']['funding_to_reserve']=='0.00'
    assert rows['Collections delayed']['minimum_cash']=='-30.00'
    assert rows['Collections delayed']['funding_to_reserve']=='70.00'
    assert rows['Collections delayed']['deferred_beyond_horizon']=='30.00'
    combined=rows['Combined stress']
    assert combined['minimum_cash']=='-50.00'
    assert combined['funding_to_reserve']=='90.00'
    assert combined['first_reserve_breach']=='2026-09-07'
    assert combined['weeks'][2]['inflow']=='50.00'
    assert combined['deferred_beyond_horizon']=='15.00'
    saved=next(r for r in c.get('/runs',headers=h).json() if r['id']==response.json()['id'])
    assert saved['output']['source_forecast_id']==forecast
    auditor,_=member(c,h,slug,'auditor')
    assert c.post('/cash/stress',headers=auditor,json=body).status_code==403
    assert c.post('/cash/stress',json=body).status_code==401
    assert c.post('/cash/stress',headers=h,json={**body,'reserve':'-1'}).status_code==422
    assert c.post('/cash/stress',headers=h,json={**body,'collection_delay_weeks':13}).status_code==422
    assert c.post('/cash/stress',headers=h,json={**body,'forecast_id':response.json()['id']}).status_code==422
    assert c.post('/cash/stress',headers=h,json={**body,'forecast_id':'foreign'}).status_code==404
    opening=c.post('/cash/stress',headers=h,json={**body,'reserve':'60'}).json()
    assert opening['scenarios'][0]['first_reserve_breach']=='opening'
