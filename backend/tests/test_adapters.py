import httpx, json, uuid, pytest
from app.erp import BusinessCentralConnector, NetSuiteConnector, ConnectorError
from app.agents import investigate
from app.platform_models import Finding, PlatformEvent, Account, LegalEntity, User
from app.database import SessionLocal
from app.auth import Principal
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from test_platform import workspace, journal, ingest


def test_business_central_pagination_auth_and_normalization():
    tenant=str(uuid.uuid4());company=str(uuid.uuid4());calls=[]
    def provider(request):
        calls.append(request)
        assert request.headers['Authorization']=='Bearer test-token'
        return httpx.Response(200,json={'value':[{'accountNumber':'BANK','documentNumber':'J1','postingDate':'2026-10-01','amount':'100.10'},{'accountNumber':'REV','documentNumber':'J1','postingDate':'2026-10-01','amount':'-100.10'}]})
    connector=BusinessCentralConnector({'tenant_id':tenant,'company_id':company,'environment':'Production','account_mapping':{'BANK':'1000','REV':'4000'}},'test-token',httpx.MockTransport(provider))
    page=connector.fetch_page();entries=connector.normalize(page['rows'],'USD')
    assert len(entries)==1 and entries[0]['lines'][0]['account_code']=='1000'
    assert entries[0]['lines'][1]['credit']=='100.10'
    with pytest.raises(ConnectorError,match='Unsafe'): connector.fetch_page('https://example.com/steal-token')
    connector.close()


def test_netsuite_suiteql_pagination_contract(monkeypatch):
    monkeypatch.setenv('FINANCE_QUERY_TEST','SELECT id AS external_id FROM Transaction')
    def provider(request):
        assert request.method=='POST' and request.headers['Prefer']=='transient'
        assert json.loads(request.content)['q'].startswith('SELECT ')
        return httpx.Response(200,json={'items':[{'external_id':'1','posting_date':'2026-10-01','account_code':'1000','debit':'100','credit':'0'}],'hasMore':True})
    connector=NetSuiteConnector({'account_id':'123456-sb1','query_env':'FINANCE_QUERY_TEST'},'test-token',httpx.MockTransport(provider))
    page=connector.fetch_page();assert page['cursor']=='1';assert connector.normalize(page['rows'],'USD')[0]['external_id']=='1'
    connector.close()


def test_ai_rejects_fabricated_citations(workspace,monkeypatch):
    c,h,e,_,_=workspace
    body=journal();assert ingest(c,h,e,[body]).status_code==200
    duplicate=journal('OTHER');duplicate['lines']=body['lines'];assert ingest(c,h,e,[duplicate]).status_code==200
    finding=c.get('/integrity/findings',headers=h).json()[0]
    monkeypatch.setenv('OPENAI_API_KEY','test-only-key');monkeypatch.setenv('OPENAI_MODEL','test-model')
    def provider(request):
        payload=json.loads(request.content);assert payload['store'] is False and not payload.get('tools')
        output={'explanation':'Review possible duplicate','recommendation':'Ask controller','evidence_ids':['invented-source'],'limitations':'Uncertain'}
        return httpx.Response(200,json={'status':'completed','model':'test-model','output':[{'content':[{'type':'output_text','text':json.dumps(output)}]}]})
    with SessionLocal() as db:
        item=db.get(Finding,finding['id']);actor=Principal(item.org_id,'test','owner','Test')
        with pytest.raises(ValueError,match='unavailable evidence'): investigate(db,actor,item,'openai',httpx.MockTransport(provider))


def test_storage_rejects_cross_org_reference(workspace):
    c,h,e,u,_=workspace
    other=c.post('/auth/register',json={'organization':'Other','slug':'foreign-'+uuid.uuid4().hex[:10],'name':'Other','email':'other@example.com','password':'Long-password-123'}).json()['user']
    with SessionLocal() as db:
        db.add(Account(id=str(uuid.uuid4()),org_id=other['org_id'],entity_id=e,code='FORGED',name='Cross tenant',category='asset',group_code='1000',is_cash=False))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()


def test_audit_hash_detects_sql_tampering(workspace):
    c,h,_,u,_=workspace
    assert c.get('/audit/verify',headers=h).json()['valid']
    with SessionLocal() as db:
        event=db.scalar(select(PlatformEvent).where(PlatformEvent.org_id==u['org_id']))
        db.execute(update(PlatformEvent).where(PlatformEvent.id==event.id).values(action='tampered'));db.commit()
    assert not c.get('/audit/verify',headers=h).json()['valid']


def test_completed_sync_is_atomic_and_idempotent(workspace,monkeypatch):
    import app.main as api
    c,h,e,u,_=workspace
    secret='FINANCE_SECRET_'+u['org_id'].replace('-','').upper()+'_BC';monkeypatch.setenv(secret,'mock-secret')
    class MockConnector:
        def __init__(self,config,secret): pass
        def close(self): pass
        def fetch_page(self,cursor=None): return {'rows':[{'id':'mock'}],'cursor':None}
        def normalize(self,rows,currency): return [journal('SYNC1')]
    monkeypatch.setitem(api.CONNECTORS,'business_central',MockConnector)
    connection=c.post('/connections',headers=h,json={'entity_id':e,'name':'Mocked BC','provider':'business_central','credential_env':secret,'config':{'tenant_id':str(uuid.uuid4()),'company_id':str(uuid.uuid4()),'environment':'Production'}}).json()['id']
    for expected in (1,0):
        job=c.post('/connections/'+connection+'/sync',headers=h).json()['id']
        result=c.post('/sync/jobs/'+job+'/step',headers=h)
        assert result.status_code==200,result.text
        assert result.json()['status']=='complete' and result.json()['imported']==expected
    assert len(c.get('/journals',params={'entity_id':e},headers=h).json())==1

def test_postgres_money_ddl_and_bind_exactness():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    from app.platform_models import JournalLine
    from app.models import ExactMoney
    from decimal import Decimal
    dialect=postgresql.dialect()
    ddl=str(CreateTable(JournalLine.__table__).compile(dialect=dialect))
    assert 'NUMERIC(20, 2)' in ddl and 'FOREIGN KEY(org_id, account_id)' in ddl
    exact=ExactMoney().process_bind_param(Decimal('999999999999999999.99'),dialect)
    assert isinstance(exact,Decimal) and str(exact)=='999999999999999999.99'
