import json, pytest, zipfile, io, tempfile
from pathlib import Path
from cryptography.exceptions import InvalidTag, InvalidSignature
from app import pqc_security as pqc
from app.security_controls import validate_production
from test_platform import workspace, journal, ingest

@pytest.fixture
def protected_keys(monkeypatch):
    directory=tempfile.TemporaryDirectory(prefix='finance-keys-test-');path=Path(directory.name)/'keys.json';monkeypatch.setenv('FINANCE_KEYRING_FILE',str(path));pqc.load_keys.cache_clear()
    identity=pqc.initialize(path)
    yield identity
    pqc.load_keys.cache_clear();directory.cleanup()

def test_signed_close_snapshot_export(workspace,protected_keys):
    import hashlib
    c,h,e,_,_=workspace
    saved=c.post('/close/readiness',headers=h,json={'entity_id':e,'period':'2026-10'})
    assert saved.status_code==201
    result=c.get('/close/snapshots/'+saved.json()['run_id']+'/export',headers=h)
    assert result.status_code==200,result.text
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        receipt=json.loads(archive.read('pqc-receipt.json'))
        assert pqc.verify_receipt(receipt,protected_keys['signing_public_key'])
        assert receipt['payload']['files_sha512']['close-readiness.json']==hashlib.sha512(archive.read('close-readiness.json')).hexdigest()
        assert json.loads(archive.read('close-readiness.json'))['output']['ready_for_review'] is False
    assert c.get('/close/snapshots/missing/export',headers=h).status_code==404

def test_pqc_encryption_integrity_context_and_signatures(protected_keys):
    clear=b'private customer finance payload'
    sealed=pqc.seal(clear,'tenant-record')
    assert clear not in sealed and pqc.unseal(sealed,'tenant-record')==clear
    with pytest.raises(InvalidTag): pqc.unseal(sealed,'different-record')
    body=json.loads(sealed[len(pqc.PREFIX):]);cipher=bytearray(pqc.decode(body['ciphertext']));cipher[-1]^=1;body['ciphertext']=pqc.encode(cipher)
    with pytest.raises(InvalidTag): pqc.unseal(pqc.PREFIX+pqc.canonical(body),'tenant-record')
    receipt=pqc.sign_receipt({'amount':'100.00'})
    assert pqc.verify_receipt(receipt,protected_keys['signing_public_key'])
    receipt['payload']['amount']='1000.00'
    with pytest.raises(InvalidSignature): pqc.verify_receipt(receipt,protected_keys['signing_public_key'])
    with pytest.raises(ValueError): pqc.verify_receipt(receipt,'untrusted-key')

def test_encrypted_database_and_signed_package(workspace,protected_keys):
    from app.database import engine
    c,h,e,_,_=workspace
    result=ingest(c,h,e,[journal()]);assert result.status_code==200,result.text
    jid=result.json()['journal_ids'][0]
    upload=c.post('/evidence',headers=h,data={'journal_id':jid},files={'file':('private.txt',b'customer-secret-unique','text/plain')});assert upload.status_code==201,upload.text
    with engine.connect() as conn:
        source=conn.exec_driver_sql('SELECT payload FROM source_records WHERE org_id=(SELECT org_id FROM journal_entries WHERE id=?)',(jid,)).scalar()
        assert '__finance_pqc_envelope__' in source and '100.00' not in source
        blob=conn.exec_driver_sql('SELECT content FROM evidence_documents WHERE id=?',(upload.json()['id'],)).scalar()
        assert b'customer-secret-unique' not in blob
    assert c.get('/evidence/'+upload.json()['id']+'/download',headers=h).content==b'customer-secret-unique'
    archive=c.get('/audit/package',headers=h,params={'entity_id':e})
    with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
        receipt=json.loads(package.read('pqc-receipt.json'))
        assert pqc.verify_receipt(receipt,protected_keys['signing_public_key'])
        import hashlib
        assert all(hashlib.sha512(package.read(name)).hexdigest()==digest for name,digest in receipt['payload']['files_sha512'].items())

def test_security_headers_and_host_filter(workspace):
    c,h,_,_,_=workspace
    response=c.get('/entities',headers=h)
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-frame-options']=='DENY'
    assert c.get('/health',headers={'Host':'attacker.example'}).status_code==400
    assert c.post('/auth/login',headers={'Content-Length':'9000000'},content=b'{}').status_code==413
    sessions=c.get('/auth/sessions',headers=h).json()
    assert c.post('/auth/sessions/'+sessions[0]['id']+'/revoke',headers=h).status_code==200
    assert c.get('/auth/me',headers=h).status_code==401

def test_production_fails_closed_without_keys(monkeypatch):
    monkeypatch.setenv('FINANCE_ENV','production');monkeypatch.delenv('FINANCE_KEYRING_FILE',raising=False)
    with pytest.raises(RuntimeError): validate_production()
    monkeypatch.setenv('FINANCE_KEYRING_FILE',str(Path(tempfile.gettempdir())/'finance-key-missing-for-test.json'))
    with pytest.raises(RuntimeError): validate_production()

