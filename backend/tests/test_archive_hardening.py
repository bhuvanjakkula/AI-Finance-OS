import hashlib, json, zipfile, tempfile
from pathlib import Path
import pytest
from test_security import protected_keys
from app import pqc_security as pqc
from app.security_admin import verify_archive

@pytest.fixture
def archive_directory():
    with tempfile.TemporaryDirectory(prefix='finance-archive-test-') as directory:
        yield Path(directory)


def test_archive_streaming_and_tampering(protected_keys,archive_directory):
    tmp_path=archive_directory
    content=b'financial evidence'*20000
    receipt=pqc.sign_receipt({'files_sha512':{'evidence/data.bin':hashlib.sha512(content).hexdigest()}})
    public=tmp_path/'public.txt';public.write_text(protected_keys['signing_public_key'])
    archive=tmp_path/'audit.zip'
    def write(data):
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('evidence/data.bin',data)
            z.writestr('pqc-receipt.json',json.dumps(receipt))
    write(content)
    assert verify_archive(archive,public)['valid']
    write(content+b'tampered')
    with pytest.raises(ValueError,match='modified'): verify_archive(archive,public)


@pytest.mark.parametrize('name',['../data','/data','evidence\\data','C:data','evidence/./data'])
def test_reject_unsafe_signed_paths(protected_keys,archive_directory,name):
    tmp_path=archive_directory
    receipt=pqc.sign_receipt({'files_sha512':{name:hashlib.sha512(b'x').hexdigest()}})
    public=tmp_path/'public.txt';public.write_text(protected_keys['signing_public_key'])
    archive=tmp_path/'audit.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr(name,b'x');z.writestr('pqc-receipt.json',json.dumps(receipt))
    with pytest.raises(ValueError,match='Unsafe|members do not match'): verify_archive(archive,public)


def test_reject_unsigned_receipt_fields(protected_keys):
    receipt=pqc.sign_receipt({'files_sha512':{}})
    receipt['verified']=True
    with pytest.raises(ValueError,match='fields'):
        pqc.verify_receipt(receipt,protected_keys['signing_public_key'])

