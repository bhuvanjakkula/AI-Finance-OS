import pytest
from fastapi.testclient import TestClient
from app.legacy_main import app

def line(ref='valid-1', **changes):
    return dict(external_id=ref,date='2026-10-01',account='Cash',currency='USD',debit='10.25',credit='0',description='Test',**changes)

@pytest.mark.parametrize('field,value', [('date','2026-02-30'),('debit','NaN'),('debit','1.001'),('credit','-1'),('currency','123')])
def test_invalid_data(field,value):
    body=line();body[field]=value
    with TestClient(app) as c:
        assert c.post('/ledger/lines',json=[body]).status_code==422

def test_conflict_rolls_back_entire_batch():
    h={'X-Tenant-ID':'rollback'}
    with TestClient(app) as c:
        assert c.post('/ledger/lines',headers=h,json=[line()]).status_code==200
        conflict=line();conflict['debit']='99'
        assert c.post('/ledger/lines',headers=h,json=[line('new-id'),conflict]).status_code==422
        assert len(c.get('/ledger/lines',headers=h).json())==1
        assert c.post('/ledger/lines',headers=h,json=[line()]).json()['imported']==0

def test_close_isolation_and_audit():
    h={'X-Tenant-ID':'closeteam'}
    with TestClient(app) as c:
        r=c.post('/close/tasks',headers=h,json={'title':'Bank reconciliation','owner':'Alex','due_date':'2026-10-08'})
        assert r.status_code==201
        task=r.json()['id']
        assert c.patch(f'/close/tasks/{task}',headers={'X-Tenant-ID':'other'},json={'status':'complete'}).status_code==404
        assert c.patch(f'/close/tasks/{task}',headers=h,json={'status':'complete'}).status_code==200
        assert c.get('/close/tasks',headers=h).json()[0]['status']=='complete'
        assert len(c.get('/audit/events',headers=h).json())==2
        assert c.patch(f'/close/tasks/{task}',headers=h,json={'status':'invalid'}).status_code==422

def test_exact_small_amounts_export_and_exception_isolation():
    h={'X-Tenant-ID':'reports'}
    with TestClient(app) as c:
        a=line('a');a['account']='=malicious';a['debit']='0.10'
        b=line('b');b['account']='=malicious';b['debit']='0.20'
        assert c.post('/ledger/lines',headers=h,json=[a,b]).status_code==200
        row=c.get('/reports/trial-balance',headers=h).json()['rows'][0]
        assert row['balance']=='0.30'
        assert "'=malicious" in c.get('/reports/trial-balance.csv',headers=h).text
        c.post('/demo/seed',headers=h)
        exception=c.get('/exceptions',headers=h).json()[0]['id']
        assert c.post(f'/exceptions/{exception}/resolve',headers={'X-Tenant-ID':'other'}).status_code==404


def test_large_amount_preserves_cents():
    h={"X-Tenant-ID":"exactmoney"}
    body=line('large');body['debit']='999999999999999999.99'
    with TestClient(app) as c:
        assert c.post('/ledger/lines',headers=h,json=[body]).status_code==200
        assert c.get('/reports/trial-balance',headers=h).json()['rows'][0]['balance']==body['debit']


def test_csv_validation_and_atomicity():
    h={"X-Tenant-ID":"csvchecks"}
    with TestClient(app) as c:
        assert c.post('/imports/csv',headers=h,files={"file":("bad.csv",b"wrong,header\n1,2", "text/csv")}).status_code==422
        raw=b"external_id,date,account,currency,debit,credit,description\nok,2026-10-01,Cash,USD,1,0,test\nbad,invalid,Cash,USD,2,0,test\n"
        assert c.post('/imports/csv',headers=h,files={"file":("ledger.csv",raw,"text/csv")}).status_code==422
        assert c.get('/ledger/lines',headers=h).json()==[]
