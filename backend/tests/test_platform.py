import pytest, uuid, json, io, zipfile
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def workspace():
    with TestClient(app) as c:
        slug='org-'+uuid.uuid4().hex[:10]
        r=c.post('/auth/register',json={'organization':'Test Finance','slug':slug,'name':'Owner','email':'owner@example.com','password':'Correct-horse-1234'})
        assert r.status_code==201,r.text
        user=r.json()['user'];h={'Authorization':'Bearer '+r.json()['token']}
        e=c.post('/entities',headers=h,json={'code':'US','name':'US Company','currency':'USD'})
        assert e.status_code==201,e.text
        entity=e.json()['id']
        for code,name,category,cash in [('1000','Cash','asset',True),('2000','Payables','liability',False),('3000','Capital','equity',False),('4000','Revenue','revenue',False),('5000','Expenses','expense',False)]:
            assert c.post(f'/entities/{entity}/accounts',headers=h,json={'code':code,'name':name,'category':category,'group_code':code,'is_cash':cash}).status_code==201
        yield c,h,entity,user,slug

def journal(ref='J1',value='100.00'):
    return {'external_id':ref,'posting_date':'2026-10-01','currency':'USD','lines':[{'account_code':'1000','debit':value,'credit':'0','reference':ref},{'account_code':'4000','debit':'0','credit':value,'reference':ref}]}
def ingest(c,h,e,entries): return c.post('/journals/import',headers=h,json={'entity_id':e,'journals':entries})
def member(c,h,slug,role='controller'):
    email=uuid.uuid4().hex+'@example.com'
    r=c.post('/users',headers=h,json={'name':'Reviewer','email':email,'role':role,'password':'Reviewer-password-123'});assert r.status_code==201,r.text
    token=c.post('/auth/login',json={'slug':slug,'email':email,'password':'Reviewer-password-123'}).json()['token']
    return {'Authorization':'Bearer '+token},r.json()['id']

def event(e,version,operation='upsert',ref='STREAM'):
    entry=journal(ref,str(version*100));entry['version']=version
    return {'entity_id':e,'event_id':ref+'-'+str(version),'external_id':ref,'version':version,'operation':operation,'occurred_at':'2026-10-08T10:00:00Z','reason':'Source lifecycle change','journal':None if operation=='delete' else entry}

def test_event_order_replay_tombstone_and_restore(workspace):
    c,h,e,_,_=workspace
    second=event(e,2)
    assert c.post('/integration/events',headers=h,json=second).status_code==202
    assert c.post('/integration/process',headers=h).json()['processed'][0]['status']=='waiting'
    assert not c.get('/integration/status',headers=h).json()['projection_caught_up']
    first=event(e,1)
    assert c.post('/integration/events',headers=h,json=first).status_code==202
    c.post('/integration/process',headers=h)
    rows=c.get('/journals',headers=h,params={'entity_id':e}).json()
    assert len(rows)==1 and rows[0]['version']==2
    assert c.post('/integration/events',headers=h,json=first).json()['replayed']
    changed={**first,'reason':'Different payload'}
    assert c.post('/integration/events',headers=h,json=changed).status_code==409
    deleted=event(e,3,'delete')
    c.post('/integration/events',headers=h,json=deleted);c.post('/integration/process',headers=h)
    assert c.get('/journals',headers=h,params={'entity_id':e}).json()==[]
    assert len(c.get('/journals',headers=h,params={'entity_id':e,'include_history':True}).json())==2
    assert ingest(c,h,e,[event(e,4)['journal']]).status_code==409
    restored=event(e,4,'restore')
    c.post('/integration/events',headers=h,json=restored);c.post('/integration/process',headers=h)
    assert c.get('/reports/statements',headers=h,params={'entity_id':e,'period':'2026-10'}).json()['net_income']=='400.00'
    assert len(c.get('/integration/outbox',headers=h).json())==4
    assert c.get('/integration/status',headers=h).json()['projection_caught_up']

def test_manifest_anti_entropy_and_staleness(workspace):
    c,h,e,_,slug=workspace
    assert c.get('/integration/status',headers=h).json()['freshness']['upstream_status']=='unverified'
    ingest(c,h,e,[journal()])
    manifest=c.get('/integration/manifest',headers=h,params={'entity_id':e}).json()
    body={'entity_id':e,'connection_id':'manual','watermark':'checkpoint-1','observed_at':'2020-01-01T00:00:00Z','records':manifest['records']}
    r=c.post('/integration/reconcile',headers=h,json=body);assert r.status_code==200,r.text
    assert r.json()['converged']
    assert c.post('/integration/reconcile',headers=h,json=body).status_code==409
    state=c.get('/integration/status',headers=h).json()['freshness']
    assert state['sources'][0]['stale'] and state['sources'][0]['converged']
    updated=journal(value='200');updated['version']=2;ingest(c,h,e,[updated])
    assert not c.get('/integration/status',headers=h).json()['freshness']['sources'][0]['converged']
    body['observed_at']='2020-01-02T00:00:00Z';body['records'].append({'external_id':'MISSING','version':1,'payload_hash':'a'*64,'tombstone':False})
    diff=c.post('/integration/reconcile',headers=h,json=body).json()
    assert diff['missing_local']==['MISSING'] and diff['divergent'][0]['external_id']=='J1'
    body['observed_at']='2020-01-03T00:00:00Z';body['records']=[]
    assert c.post('/integration/reconcile',headers=h,json=body).json()['unexpected_local']==['J1']
    assert len(c.get('/journals',headers=h,params={'entity_id':e}).json())==1
    ah,_=member(c,h,slug,'auditor')
    assert c.post('/integration/reconcile',headers=ah,json=body).status_code==403
    assert c.post('/integration/policy',headers=ah,json={}).status_code==403
    assert c.post('/integration/policy',headers=h,json={'max_pending_seconds':0}).status_code==422
    assert c.post('/integration/policy',headers=h,json={'max_pending_seconds':10,'max_source_age_seconds':60,'reconciliation_interval_seconds':5}).json()['max_pending_seconds']==10

def test_staleness_alert_and_worker_cadence(workspace):
    from datetime import timedelta
    from app.database import SessionLocal
    from app.platform_models import IntegrationMessage, ReconciliationPolicy, now
    from app.anti_entropy import reconcile_due
    from app.auth import Principal
    c,h,e,user,_=workspace
    c.post('/integration/events',headers=h,json=event(e,2))
    with SessionLocal() as db:
        row=db.scalar(__import__('sqlalchemy').select(IntegrationMessage).where(IntegrationMessage.org_id==user['org_id']))
        row.received_at=now()-timedelta(seconds=301);db.commit()
    assert c.get('/integration/status',headers=h).json()['freshness']['pending_threshold_exceeded']
    actor=Principal(user['org_id'],user['id'],'owner','Owner')
    with SessionLocal() as db:
        result=reconcile_due(db,actor);assert result['due'] and result['freshness']['pending_threshold_exceeded'];db.commit()
        assert not reconcile_due(db,actor)['due']
    assert any(r['action']=='reconciliation_threshold_alert' for r in c.get('/audit/events',headers=h).json())

def test_blocked_streams_do_not_starve_ready_event(workspace):
    from app.database import SessionLocal
    from app.platform_models import IntegrationMessage
    from app.auth import uid
    from app.finance_engine import hash_json
    c,h,e,user,_=workspace
    with SessionLocal() as db:
        for i in range(110):
            body=event(e,2,ref='BLOCKED-'+str(i))
            db.add(IntegrationMessage(id=uid(),org_id=user['org_id'],entity_id=e,connection_id='manual',event_id=body['event_id'],external_id=body['external_id'],version=2,envelope=body,payload_hash=hash_json(body)))
        db.commit()
    # This ready revision is version 3, after the 110 blocked version-2 streams.
    first=journal('READY');second=journal('READY','200');second['version']=2
    ingest(c,h,e,[first,second])
    c.post('/integration/events',headers=h,json=event(e,3,ref='READY'))
    result=c.post('/integration/process',headers=h);assert result.status_code==200,result.text
    rows=c.get('/journals',headers=h,params={'entity_id':e}).json()
    assert rows[0]['version']==3

def test_event_conflict_dead_letter_and_atomicity(workspace):
    c,h,e,_,slug=workspace
    bad=event(e,1);bad['journal']['lines'][1]['credit']='99'
    c.post('/integration/events',headers=h,json=bad)
    for _ in range(3): c.post('/integration/process',headers=h)
    status=c.get('/integration/status',headers=h).json()
    assert status['messages'][0]['status']=='dead_letter'
    assert c.get('/integration/outbox',headers=h).json()==[]
    assert c.get('/journals',headers=h,params={'entity_id':e}).json()==[]
    ah,_=member(c,h,slug,'auditor')
    assert c.post('/integration/events',headers=ah,json=event(e,1)).status_code==403
    competing=event(e,1,ref='OTHER');c.post('/integration/events',headers=h,json=competing);c.post('/integration/process',headers=h)
    competing['event_id']='other-conflict';competing['journal']['lines'][0]['debit']='200';competing['journal']['lines'][1]['credit']='200'
    c.post('/integration/events',headers=h,json=competing);c.post('/integration/process',headers=h)
    assert c.get('/integration/status',headers=h).json()['messages'][0]['status']=='conflict'

def test_authenticated_org_scope_and_roles(workspace):
    c,h,e,user,slug=workspace
    assert c.get('/entities').status_code==401
    other=c.post('/auth/register',json={'organization':'Other','slug':'other-'+uuid.uuid4().hex[:10],'name':'Other','email':'other@example.com','password':'Long-password-123'}).json()
    oh={'Authorization':'Bearer '+other['token']}
    assert c.get('/reports/trial-balance',params={'entity_id':e},headers=oh).status_code==404
    forged={**oh,'X-Tenant-ID':user['org_id']}
    assert c.get('/journals',params={'entity_id':e},headers=forged).status_code==404
    ah,_=member(c,h,slug,'auditor')
    assert c.get('/entities',headers=ah).status_code==200
    assert c.post('/entities',headers=ah,json={'code':'BAD','name':'Bad','currency':'USD'}).status_code==403
    assert ingest(c,ah,e,[journal()]).status_code==403
    assert c.get('/ledger/lines',headers=h).status_code==404
    assert c.post('/auth/logout',headers=h).status_code==200
    assert c.get('/auth/me',headers=h).status_code==401

def test_journal_balance_idempotency_revision_and_lineage(workspace):
    c,h,e,_,_=workspace
    good=journal();bad=journal('bad');bad['lines'][1]['credit']='99'
    assert ingest(c,h,e,[good,bad]).status_code==422
    assert c.get('/journals',params={'entity_id':e},headers=h).json()==[]
    first=ingest(c,h,e,[good]);assert first.status_code==200,first.text
    assert ingest(c,h,e,[good]).json()['skipped']==1
    conflict=journal(value='200');assert ingest(c,h,e,[conflict]).status_code==409
    conflict['version']=2
    assert ingest(c,h,e,[conflict]).status_code==200
    rows=c.get('/journals',params={'entity_id':e},headers=h).json();assert len(rows)==1 and rows[0]['version']==2
    assert len(c.get('/journals',params={'entity_id':e,'include_history':True},headers=h).json())==2
    lineage=c.get('/journals/'+rows[0]['id']+'/lineage',headers=h).json();assert lineage['source']['hash_valid']
    report=c.get('/reports/statements',params={'entity_id':e,'period':'2026-10'},headers=h).json()
    assert report['net_income']=='200.00' and report['balance_check']=='0.00'

def test_statement_golden_dataset_and_precision(workspace):
    c,h,e,_,_=workspace
    opening=journal('OPEN','999999999999999999.99');opening['lines'][1]['account_code']='3000'
    assert ingest(c,h,e,[opening]).status_code==200
    spend={'external_id':'BILL','posting_date':'2026-10-02','currency':'USD','lines':[{'account_code':'5000','debit':'0.30','credit':'0'},{'account_code':'2000','debit':'0','credit':'0.30'}]}
    assert ingest(c,h,e,[spend,journal('SALE','0.30')]).status_code==200
    s=c.get('/reports/statements',params={'entity_id':e,'period':'2026-10'},headers=h).json()
    assert s['assets']=='1000000000000000000.29';assert s['net_income']=='0.00';assert s['balance_check']=='0.00'
    assert c.get('/reports/statements',params={'entity_id':e,'period':'2026-13'},headers=h).status_code==422

def test_independent_approval_and_no_posting(workspace):
    c,h,e,_,slug=workspace
    response=c.post('/proposals',headers=h,json={'entity_id':e,'reason':'Correct invoice reference','journal':journal()});assert response.status_code==201,response.text
    identifier=response.json()['id'];url='/proposals/'+identifier+'/decision';decision={'decision':'approved','note':'Evidence reviewed'}
    assert c.post(url,headers=h,json=decision).status_code==403
    reviewer,_=member(c,h,slug)
    assert c.post(url,headers=reviewer,json=decision).json()['posted_to_erp'] is False
    assert c.post(url,headers=reviewer,json=decision).status_code==409
    assert c.get('/proposals/'+identifier+'/export',headers=reviewer).status_code==200
    assert c.get('/journals',params={'entity_id':e},headers=h).json()==[]

def test_close_dependencies(workspace):
    c,h,e,u,_=workspace
    task={'entity_id':e,'title':'Reconcile cash','owner_id':u['id'],'due_date':'2026-10-08','period':'2026-10'}
    first=c.post('/close/tasks',headers=h,json=task).json()['id']
    task['title']='Sign off';task['depends_on']=[first];second=c.post('/close/tasks',headers=h,json=task).json()['id']
    assert c.patch('/close/tasks/'+second,headers=h,json={'status':'complete'}).status_code==409
    assert c.patch('/close/tasks/'+first,headers=h,json={'status':'complete'}).status_code==200
    assert c.patch('/close/tasks/'+second,headers=h,json={'status':'complete'}).status_code==200
    assert c.patch('/close/tasks/'+first,headers=h,json={'status':'todo'}).status_code==409

def test_bank_exact_matching_and_ambiguity(workspace):
    c,h,e,_,_=workspace
    assert ingest(c,h,e,[journal()]).status_code==200
    r=c.post('/bank/import',headers=h,json={'entity_id':e,'transactions':[{'external_id':'B1','date':'2026-10-02','amount':'100','reference':'J1','currency':'USD'},{'external_id':'B2','date':'2026-10-02','amount':'99','reference':'J1','currency':'USD'}]});assert r.status_code==200,r.text
    banks=c.get('/reconciliation',params={'entity_id':e},headers=h).json()['transactions'];assert len(banks[0]['suggestions'])==1 and not banks[1]['suggestions']
    line=banks[0]['suggestions'][0]['line_id']
    assert c.post('/reconciliation/matches',headers=h,json={'bank_id':banks[1]['id'],'line_id':line}).status_code==422
    assert c.post('/reconciliation/matches',headers=h,json={'bank_id':banks[0]['id'],'line_id':line}).status_code==201
    assert c.post('/reconciliation/matches',headers=h,json={'bank_id':banks[0]['id'],'line_id':line}).status_code==409
    assert c.get('/reconciliation',params={'entity_id':e},headers=h).json()['transactions'][0]['status']=='matched'

def test_evidence_and_hash_chain(workspace):
    c,h,e,_,_=workspace
    identifier=ingest(c,h,e,[journal()]).json()['journal_ids'][0]
    assert len(c.get('/audit/gaps',params={'entity_id':e},headers=h).json())==1
    r=c.post('/evidence',headers=h,data={'journal_id':identifier},files={'file':('../../invoice.txt',b'invoice evidence','text/plain')});assert r.status_code==201,r.text
    assert c.get('/audit/gaps',params={'entity_id':e},headers=h).json()==[]
    verify=c.get('/audit/verify',headers=h).json();assert verify['valid'],verify
    package=c.get('/audit/package',params={'entity_id':e},headers=h)
    with zipfile.ZipFile(io.BytesIO(package.content)) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read('manifest.json'));assert manifest[0]['sha256']==r.json()['sha256']
        assert z.read(manifest[0]['path'])==b'invoice evidence'

def test_forecast_scenarios_and_group_rates(workspace):
    c,h,e,_,_=workspace
    assert c.post('/cash/payments',headers=h,json={'entity_id':e,'reference':'AR','due_date':'2026-10-09','amount':'100','direction':'inflow'}).status_code==201
    assert c.post('/cash/payments',headers=h,json={'entity_id':e,'reference':'AP','due_date':'2026-10-10','amount':'50','direction':'outflow'}).status_code==201
    body={'entity_id':e,'start_date':'2026-10-08','opening_cash':'0','collection_delay_days':7,'inflow_factor':'0.8'}
    r=c.post('/cash/forecast',headers=h,json=body);assert r.status_code==200,r.text
    output=r.json();assert len(output['weeks'])==13 and output['weeks'][0]['closing']=='-50.00' and output['weeks'][1]['closing']=='30.00'
    ingest(c,h,e,[journal()])
    r=c.post('/consolidation/runs',headers=h,json={'entity_ids':[e],'period':'2026-10','group_currency':'EUR','rates':{e:'0.9'}})
    assert r.status_code==200,r.text
    assert sorted(x['balance'] for x in r.json()['rows'] if Decimal(x['balance']))==['-90.00','90.00']
    assert c.post('/consolidation/runs',headers=h,json={'entity_ids':[e],'period':'2026-10','group_currency':'EUR','rates':{}}).status_code==422

def test_legacy_mapping_and_grounded_rule_agent(workspace,monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    c,h,e,_,_=workspace
    raw=b'voucher_no,date,account,dr,cr\nCSV1,2026-10-01,1000,100,0\nCSV1,2026-10-01,4000,0,100\n'
    r=c.post('/legacy/preview',headers=h,data={'entity_id':e},files={'file':('legacy.csv',raw,'text/csv')});assert r.status_code==200,r.text
    assert r.json()['valid']
    assert ingest(c,h,e,r.json()['journals']).status_code==200
    duplicate=journal('DUP');duplicate['lines'][0]['reference']='';duplicate['lines'][1]['reference']=''
    assert ingest(c,h,e,[duplicate]).status_code==200
    findings=c.get('/integrity/findings',headers=h).json();assert findings
    r=c.post('/agents/investigate',headers=h,json={'finding_id':findings[0]['id'],'provider':'rules'});assert r.status_code==200,r.text
    assert r.json()['usage']['model']=='rules-v2';assert r.json()['recommendation']['evidence_ids']
    assert c.post('/agents/investigate',headers=h,json={'finding_id':findings[0]['id'],'provider':'openai'}).status_code==502

def test_sync_failure_retries_and_dead_letter(workspace):
    c,h,e,u,_=workspace
    env='FINANCE_SECRET_'+u['org_id'].replace('-','').upper()+'_BC'
    body={'entity_id':e,'name':'Business Central','provider':'business_central','credential_env':env,'config':{'tenant_id':str(uuid.uuid4()),'company_id':str(uuid.uuid4()),'environment':'Production'}}
    r=c.post('/connections',headers=h,json=body);assert r.status_code==201,r.text
    connection=r.json()['id'];job=c.post('/connections/'+connection+'/sync',headers=h).json()['id']
    for expected in ['failed','failed','dead_letter']:
        assert c.post('/sync/jobs/'+job+'/step',headers=h).json()['status']==expected
    assert c.post('/sync/jobs/'+job+'/step',headers=h).status_code==409
    assert c.get('/journals',params={'entity_id':e},headers=h).json()==[]
