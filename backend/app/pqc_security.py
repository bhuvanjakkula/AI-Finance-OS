"""Versioned ML-KEM/AES-GCM storage envelopes and ML-DSA audit signatures.

Uses cryptography's native primitives; this storage format requires independent
review before production. It is not TLS, an HSM, or a FIPS-validated module.
"""
import base64, hashlib, json, os
from functools import lru_cache
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey
from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA65PrivateKey, MLDSA65PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import TypeDecorator, JSON, LargeBinary

SUITE='ML-KEM-768/HKDF-SHA256/AES-256-GCM/v1'
PREFIX=b'FINANCE-PQC1\x00'
def encode(value): return base64.b64encode(value).decode('ascii')
def decode(value): return base64.b64decode(value,validate=True)
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def key_path():
    local=Path(os.getenv('LOCALAPPDATA',str(Path.home()/'.local/share')))/'AIFinanceOS/security/keyring.json'
    return Path(os.getenv('FINANCE_KEYRING_FILE',str(local)))
@lru_cache(maxsize=4)
def load_keys(path):
    data=json.loads(Path(path).read_text())
    if data.get('format')!='finance-keyring-v1': raise ValueError('Invalid keyring format')
    return data,MLKEM768PrivateKey.from_seed_bytes(decode(data['kem_seed'])),MLDSA65PrivateKey.from_seed_bytes(decode(data['signing_seed']))
def keys():
    path=key_path()
    if not path.is_file():
        if os.getenv('FINANCE_ENV')=='production' or os.getenv('FINANCE_REQUIRE_ENCRYPTION','true').lower()=='true': raise RuntimeError('Encryption keyring required; initialize offline before starting')
        return None
    return load_keys(str(path.resolve()))
def initialize(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    kem=MLKEM768PrivateKey.generate();sign=MLDSA65PrivateKey.generate()
    data={'format':'finance-keyring-v1','key_id':os.urandom(16).hex(),'kem_seed':encode(kem.private_bytes_raw()),'signing_seed':encode(sign.private_bytes_raw())}
    with path.open('x',encoding='utf-8') as file: json.dump(data,file)
    if os.name!='nt': path.chmod(0o600)
    return {'key_id':data['key_id'],'signing_public_key':encode(sign.public_key().public_bytes_raw())}
def seal(content,context):
    loaded=keys()
    if loaded is None: return content
    data,kem,_=loaded
    secret,encapsulation=kem.public_key().encapsulate()
    nonce=os.urandom(12)
    header={'suite':SUITE,'key_id':data['key_id'],'kem':encode(encapsulation),'nonce':encode(nonce)}
    aad=canonical(header)+b'\x00'+context.encode()
    key=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=b'finance-storage-v1').derive(secret)
    header['ciphertext']=encode(AESGCM(key).encrypt(nonce,content,aad))
    return PREFIX+canonical(header)
def unseal(content,context):
    if not content.startswith(PREFIX):
        if os.getenv('FINANCE_ENV')=='production': raise ValueError('Unencrypted legacy data requires migration')
        return content
    loaded=keys()
    if loaded is None: raise RuntimeError('Encrypted storage key unavailable')
    data,kem,_=loaded;header=json.loads(content[len(PREFIX):])
    if header['suite']!=SUITE or header['key_id']!=data['key_id']: raise ValueError('Unknown crypto suite or key ID')
    ciphertext=decode(header.pop('ciphertext'));aad=canonical(header)+b'\x00'+context.encode()
    secret=kem.decapsulate(decode(header['kem']))
    key=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=b'finance-storage-v1').derive(secret)
    return AESGCM(key).decrypt(decode(header['nonce']),ciphertext,aad)
def sign_receipt(payload):
    loaded=keys()
    if loaded is None: raise RuntimeError('PQC signing key unavailable')
    data,_,signing=loaded
    message={'format':'finance-audit-receipt-v1','algorithm':'ML-DSA-65','key_id':data['key_id'],'payload':payload}
    return {**message,'public_key':encode(signing.public_key().public_bytes_raw()),'signature':encode(signing.sign(canonical(message),context=b'finance-audit-v1'))}
def verify_receipt(receipt,trusted_public_key):
    if not isinstance(receipt,dict) or set(receipt)!={'format','algorithm','key_id','payload','public_key','signature'}:
        raise ValueError('Invalid receipt fields')
    if not isinstance(receipt['payload'],dict) or not isinstance(receipt['key_id'],str) or len(receipt['key_id'])!=32:
        raise ValueError('Invalid receipt metadata')
    if receipt['public_key']!=trusted_public_key: raise ValueError('Signing identity does not match pinned key')
    message={k:receipt[k] for k in ('format','algorithm','key_id','payload')}
    if message['format']!='finance-audit-receipt-v1' or message['algorithm']!='ML-DSA-65': raise ValueError('Unknown signature format')
    MLDSA65PublicKey.from_public_bytes(decode(trusted_public_key)).verify(decode(receipt['signature']),canonical(message),context=b'finance-audit-v1')
    return True

class EncryptedJSON(TypeDecorator):
    impl=JSON
    cache_ok=True
    def __init__(self,context): self.context=context;super().__init__()
    def process_bind_param(self,value,dialect):
        if value is None: return None
        raw=seal(canonical(value),self.context)
        return {'__finance_pqc_envelope__':encode(raw)} if raw.startswith(PREFIX) else value
    def process_result_value(self,value,dialect):
        if value is None: return None
        if isinstance(value,dict) and '__finance_pqc_envelope__' in value:
            return json.loads(unseal(decode(value['__finance_pqc_envelope__']),self.context))
        if os.getenv('FINANCE_ENV')=='production': raise ValueError('Unencrypted legacy JSON requires migration')
        return value
class EncryptedBinary(TypeDecorator):
    impl=LargeBinary
    cache_ok=True
    def __init__(self,context): self.context=context;super().__init__()
    def process_bind_param(self,value,dialect): return seal(value,self.context) if value is not None else None
    def process_result_value(self,value,dialect): return unseal(bytes(value),self.context) if value is not None else None
