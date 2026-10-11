from test_platform import workspace, journal, ingest, member

def test_frozen_review_changes_and_policy_disclosure(workspace):
    c,h,e,_,slug=workspace
    ingest(c,h,e,[journal(value='100')])
    body={'entity_id':e,'period':'2026-10','materiality':'50'}
    first=c.post('/reports/budget-exceptions',headers=h,json=body).json()['id']
    revised=journal(value='120');revised['version']=2;ingest(c,h,e,[revised])
    last=c.post('/reports/budget-exceptions',headers=h,json={**body,'materiality':'200'}).json()['id']
    params={'earlier_id':first,'later_id':last}
    r=c.get('/reports/budget-review-changes',headers=h,params=params)
    assert r.status_code==200,r.text
    revenue=next(row for row in r.json()['rows'] if row['code']=='4000')
    assert revenue['actual_before']=='100.00' and revenue['actual_after']=='120.00'
    assert revenue['actual_change']=='20.00'
    assert revenue['review_before'] and not revenue['review_after']
    assert r.json()['materiality_after']=='200.00'
    assert c.get('/reports/budget-review-changes',headers=h,params={'earlier_id':first,'later_id':first}).status_code==422
    assert c.get('/reports/budget-review-changes',headers=h,params={'earlier_id':last,'later_id':first}).status_code==422
    assert c.get('/reports/budget-review-changes',headers=h,params={**params,'later_id':'foreign'}).status_code==404
    assert c.get('/reports/budget-review-changes',params=params).status_code==401
    auditor,_=member(c,h,slug,'auditor')
    assert c.get('/reports/budget-review-changes',headers=auditor,params=params).status_code==200
