from datetime import datetime, timezone
from test_platform import workspace, journal, ingest, member

def test_close_history_scoped_by_period_and_entity(workspace):
    c,h,e,_,_=workspace
    saved=c.post('/close/readiness',headers=h,json={'entity_id':e,'period':'2026-10'}).json()
    rows=c.get('/close/snapshots',headers=h,params={'entity_id':e,'period':'2026-10'})
    assert rows.status_code==200
    assert rows.json()[0]['id']==saved['run_id']
    assert c.get('/close/snapshots',headers=h,params={'entity_id':e,'period':'2026-09'}).json()==[]
    assert c.get('/close/snapshots',headers=h,params={'entity_id':'foreign-entity','period':'2026-10'}).status_code==404
    assert c.get('/close/snapshots',params={'entity_id':e,'period':'2026-10'}).status_code==401

def test_unfinished_import_blocks_until_complete(workspace):
    from app.database import SessionLocal
    from app.platform_models import ERPConnection, SyncJob, LegalEntity
    from app.auth import uid
    c,h,e,_,_=workspace
    with SessionLocal() as db:
        org=db.get(LegalEntity,e).org_id
        connection=ERPConnection(id=uid(),org_id=org,entity_id=e,name='Test source',provider='netsuite',config={},credential_env='FINANCE_SECRET_TEST')
        db.add(connection);db.flush()
        job=SyncJob(id=uid(),org_id=org,connection_id=connection.id,status='failed',result={})
        db.add(job);db.commit();job_id=job.id
    status=c.get('/close/readiness',headers=h,params={'entity_id':e,'period':'2026-10'}).json()
    check=next(r for r in status['checks'] if r['code']=='sync')
    assert not check['passed'] and check['affected_ids']==[job_id]
    assert check['module']=='ERP Integration'
    with SessionLocal() as db:
        db.get(SyncJob,job_id).status='complete';db.commit()
    status=c.get('/close/readiness',headers=h,params={'entity_id':e,'period':'2026-10'}).json()
    assert next(r for r in status['checks'] if r['code']=='sync')['passed']

def test_empty_close_is_blocked_and_tenant_scoped(workspace):
    c,h,e,_,slug=workspace
    status=c.get('/close/readiness',headers=h,params={'entity_id':e,'period':'2026-10'})
    assert status.status_code==200
    assert {'ledger','tasks','coverage','freshness'} <= set(status.json()['blockers'])
    assert c.get('/close/readiness',headers=h,params={'entity_id':'other-entity','period':'2026-10'}).status_code==404
    auditor,_=member(c,h,slug,'auditor')
    assert c.post('/close/readiness',headers=auditor,json={'entity_id':e,'period':'2026-10'}).status_code==403

def test_readiness_rechecks_sources_and_saves_immutable_snapshot(workspace):
    c,h,e,user,_=workspace
    ingest(c,h,e,[journal()])
    task=c.post('/close/tasks',headers=h,json={'entity_id':e,'title':'Review October','owner_id':user['id'],'due_date':'2026-10-31','period':'2026-10'}).json()
    c.patch('/close/tasks/'+task['id'],headers=h,json={'status':'complete'})
    journal_id=c.get('/journals',headers=h,params={'entity_id':e}).json()[0]['id']
    c.post('/evidence',headers=h,data={'journal_id':journal_id},files={'file':('receipt.txt',b'receipt','text/plain')})
    manifest=c.get('/integration/manifest',headers=h,params={'entity_id':e}).json()
    body={'entity_id':e,'connection_id':'manual','watermark':'verified-1','observed_at':datetime.now(timezone.utc).isoformat(),'records':manifest['records']}
    assert c.post('/integration/reconcile',headers=h,json=body).status_code==200
    saved=c.post('/close/readiness',headers=h,json={'entity_id':e,'period':'2026-10'})
    assert saved.status_code==201,saved.text
    assert saved.json()['ready_for_review'],saved.text
    # Revision changes current projection, but never rewrites prior snapshot.
    revised=journal(value='120.00');revised['version']=2
    assert ingest(c,h,e,[revised]).status_code==200
    current=c.get('/close/readiness',headers=h,params={'entity_id':e,'period':'2026-10'}).json()
    assert {'freshness','evidence'} <= set(current['blockers'])
    snapshot=next(r for r in c.get('/runs',headers=h).json() if r['id']==saved.json()['run_id'])
    assert snapshot['output']['ready_for_review']
