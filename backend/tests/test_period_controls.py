from test_platform import workspace, journal, ingest, member, event
from app import close_readiness

def test_period_independence_and_locked_imports(workspace,monkeypatch):
    c,h,e,_,slug=workspace
    body={'entity_id':e,'period':'2026-10','action':'submit','note':'Review October books'}
    assert c.post('/close/period-control',headers=h,json=body).status_code==409
    ingest(c,h,e,[journal()])
    monkeypatch.setattr(close_readiness,'assess',lambda *args:{'ready_for_review':True})
    assert c.post('/close/period-control',headers=h,json=body).json()['status']=='review'
    assert ingest(c,h,e,[journal('NEW')]).status_code==409
    assert c.post('/close/period-control',headers=h,json={**body,'action':'approve'}).status_code==403
    reviewer,_=member(c,h,slug,'controller')
    assert c.post('/close/period-control',headers=reviewer,json={**body,'action':'approve'}).json()['status']=='locked'
    revised=journal();revised['version']=2;revised['posting_date']='2026-11-01'
    assert ingest(c,h,e,[revised]).status_code==409
    assert c.post('/bank/import',headers=h,json={'entity_id':e,'transactions':[{'external_id':'B1','date':'2026-10-01','amount':'100','currency':'USD','reference':'J1'}]}).status_code==409
    assert c.post('/close/period-control',headers=reviewer,json={**body,'action':'reopen'}).status_code==403
    assert c.post('/close/period-control',headers=h,json={**body,'action':'reopen'}).json()['status']=='open'
    assert ingest(c,h,e,[revised]).status_code==200
    assert c.get('/close/period-control',headers=h,params={'entity_id':'foreign','period':'2026-10'}).status_code==404
    assert c.get('/close/period-control',params={'entity_id':e,'period':'2026-10'}).status_code==401
