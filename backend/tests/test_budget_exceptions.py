from test_platform import workspace, journal, ingest, member

def test_budget_materiality_missing_and_revenue_sign(workspace):
    c,h,e,_,slug=workspace
    ingest(c,h,e,[journal(value='100')])
    assert c.post('/budgets',headers=h,json={'entity_id':e,'period':'2026-10','account_code':'4000','amount':'150','version':1}).status_code==201
    body={'entity_id':e,'period':'2026-10','materiality':'50'}
    r=c.post('/reports/budget-exceptions',headers=h,json=body)
    assert r.status_code==201,r.text
    revenue=next(row for row in r.json()['rows'] if row['code']=='4000')
    assert revenue['earnings_impact']=='-50.00' and revenue['review_required']
    assert r.json()['budgeted_earnings_impact']=='-50.00'
    assert c.post('/reports/budget-exceptions',headers=h,json={**body,'materiality':'50.01'}).json()['exceptions']==0
    assert c.post('/reports/budget-exceptions',headers=h,json={**body,'entity_id':'foreign'}).status_code==404
    assert c.post('/reports/budget-exceptions',headers=h,json={**body,'materiality':'-1'}).status_code==422
    auditor,_=member(c,h,slug,'auditor')
    assert c.post('/reports/budget-exceptions',headers=auditor,json=body).status_code==403
    assert c.post('/reports/budget-exceptions',json=body).status_code==401
    assert c.post('/reports/budget-exceptions',headers=h,json={**body,'period':'2026-09'}).json()['unbudgeted_accounts']>0
