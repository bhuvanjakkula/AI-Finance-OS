"""Offline operator key initialization and storage migration. Stop services first."""
import argparse, json, os, sqlite3, tempfile, time
from pathlib import Path
from sqlalchemy import MetaData, select, update
from .database import engine
from . import platform_models
from .pqc_security import initialize, key_path, keys, seal, unseal, EncryptedJSON, EncryptedBinary, encode, verify_receipt

def encrypted_backup(output):
    if engine.dialect.name!='sqlite': raise RuntimeError('SQLite backup only; PostgreSQL requires a deployment-specific procedure')
    if keys() is None: raise RuntimeError('Encryption keys required')
    target=sqlite3.connect(':memory:');source=sqlite3.connect(engine.url.database)
    try:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise RuntimeError('Backup integrity check failed')
        encrypted=seal(target.serialize(),'finance-sqlite-backup-v1')
        with Path(output).open('xb') as file: file.write(encrypted)
    finally: source.close();target.close()
    return {'encrypted_backup':str(output),'verified_before_encryption':True}

def verify_backup(path):
    content=Path(path).read_bytes()
    if not content.startswith(b'FINANCE-PQC1\x00'): raise ValueError('Only encrypted backups accepted')
    target=sqlite3.connect(':memory:')
    try:
        target.deserialize(unseal(content,'finance-sqlite-backup-v1'))
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Recovered database integrity failed')
        tables=target.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        return {'recovery_verified':True,'tables':tables,'scope':'Decrypted and integrity-checked in memory; no live database overwritten'}
    finally: target.close()

def export_public():
    import hashlib
    data,_,sign=keys();public=sign.public_key().public_bytes_raw()
    path=key_path().with_name('signing-public-key.txt');path.write_text(encode(public))
    return {'key_id':data['key_id'],'public_key_file':str(path),'public_key_sha512':hashlib.sha512(public).hexdigest()}

def verify_archive(path,trusted_key_file):
    import zipfile, hashlib
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or len(names)>10000 or sum(i.file_size for i in archive.infolist())>200_000_000: raise ValueError('Archive exceeds verification bounds or has duplicate names')
        if any(not name or name.startswith(('/', '\\')) or '\\' in name or ':' in name or any(part in ('','.', '..') for part in name.split('/')) for name in names):
            raise ValueError('Unsafe archive member path')
        if archive.getinfo('pqc-receipt.json').file_size>1_000_000:
            raise ValueError('Receipt exceeds verification bounds')
        receipt=json.loads(archive.read('pqc-receipt.json'))
        verify_receipt(receipt,Path(trusted_key_file).read_text().strip())
        expected=receipt['payload']['files_sha512']
        if not isinstance(expected,dict) or any(not isinstance(value,str) or len(value)!=128 or any(c not in '0123456789abcdef' for c in value) for value in expected.values()):
            raise ValueError('Invalid signed digest manifest')
        if set(expected)!=set(names)-{'pqc-receipt.json'}: raise ValueError('Archive members do not match signed manifest')
        total=0
        for name,digest in expected.items():
            hashed=hashlib.sha512()
            with archive.open(name) as member:
                while chunk:=member.read(65536):
                    total+=len(chunk)
                    if total>200_000_000: raise ValueError('Expanded archive exceeds verification bounds')
                    hashed.update(chunk)
            if hashed.hexdigest()!=digest: raise ValueError('Archive member modified')
        return {'valid':True,'key_id':receipt['key_id'],'files':len(expected)}

def migrate_storage():
    if keys() is None: raise RuntimeError('Initialize and protect a keyring before migration')
    if engine.dialect.name!='sqlite': raise RuntimeError('PostgreSQL migration requires a reviewed deployment-specific backup procedure')
    # Consistent backup is encrypted directly; temporary plaintext copy is removed.
    db_path=Path(engine.url.database).resolve()
    backup=key_path().parent/f'pre-encryption-backup-{time.time_ns()}.pqc'
    handle,temp_path=tempfile.mkstemp(suffix='.db',dir=key_path().parent);os.close(handle)
    try:
        source=sqlite3.connect(db_path);target=sqlite3.connect(temp_path)
        try: source.backup(target)
        finally: target.close();source.close()
        backup.write_bytes(seal(Path(temp_path).read_bytes(),'finance-sqlite-backup-v1'))
    finally: Path(temp_path).unlink(missing_ok=True)
    raw=MetaData();raw.reflect(bind=engine)
    counts={}
    with engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA secure_delete=ON')
        for table in platform_models.Base.metadata.sorted_tables:
            if table.name not in raw.tables: continue
            fields=[c for c in table.columns if isinstance(c.type,(EncryptedJSON,EncryptedBinary))]
            if not fields: continue
            reflected=raw.tables[table.name];count=0
            for row in conn.execute(select(reflected)).mappings().all():
                values={}
                for col in fields:
                    value=row[col.name]
                    if value is None: continue
                    if isinstance(col.type,EncryptedJSON) and not(isinstance(value,dict) and '__finance_pqc_envelope__' in value): values[col.name]=value
                    elif isinstance(col.type,EncryptedBinary) and not bytes(value).startswith(b'FINANCE-PQC1\x00'): values[col.name]=value
                if values:
                    where=[table.c[c.name]==row[c.name] for c in table.primary_key.columns]
                    conn.execute(update(table).where(*where).values(**values));count+=1
            counts[table.name]=count
    with engine.connect() as conn: conn.exec_driver_sql('VACUUM')
    return {'encrypted_rows':counts,'encrypted_backup':str(backup),'scope':'JSON payloads and evidence; indexed scalar fields remain plaintext'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['init','migrate','public','verify','backup','verify-backup'])
    parser.add_argument('--archive')
    parser.add_argument('--trusted-key')
    parser.add_argument('--output')
    args=parser.parse_args()
    if args.action=='init': result=initialize(key_path())
    elif args.action=='migrate': result=migrate_storage()
    elif args.action=='public': result=export_public()
    elif args.action=='backup':
        if not args.output: parser.error('backup requires --output')
        result=encrypted_backup(args.output)
    elif args.action=='verify-backup':
        if not args.archive: parser.error('verify-backup requires --archive')
        result=verify_backup(args.archive)
    else:
        if not args.archive or not args.trusted_key: parser.error('verify requires --archive and --trusted-key')
        result=verify_archive(args.archive,args.trusted_key)
    if args.action=='init':
        from .pqc_security import decode
        import hashlib
        public=result.pop('signing_public_key')
        key_path().with_name('signing-public-key.txt').write_text(public)
        result['public_key_sha512']=hashlib.sha512(decode(public)).hexdigest()
    print(json.dumps(result))
