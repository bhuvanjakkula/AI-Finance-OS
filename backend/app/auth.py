"""Server-derived organization scope, salted passwords, expiring opaque sessions."""
import hashlib, hmac, os, secrets, uuid, time, threading
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import SessionLocal
from .platform_models import User, Organization, AuthSession

def uid(): return str(uuid.uuid4())
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def session_identifier(token_hash): return digest('finance-session-public-v1:'+token_hash)
def password_hash(password):
    salt=secrets.token_hex(16)
    key=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return salt+':'+key

def verify_password(password,stored):
    try:
        salt,key=stored.split(':')
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        return hmac.compare_digest(actual,key)
    except (ValueError,TypeError): return False

def db_session():
    with SessionLocal() as db:
        try: yield db
        except Exception:
            db.rollback()
            raise

@dataclass
class Principal:
    org_id: str
    user_id: str
    role: str
    name: str

def principal(authorization: str = Header(default=''), db: Session = Depends(db_session)):
    if not authorization.startswith('Bearer '): raise HTTPException(401,'Sign in required')
    session=db.get(AuthSession,digest(authorization[7:]))
    if not session or session.expires_at.replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc):
        raise HTTPException(401,'Session expired or invalid')
    user=db.get(User,session.user_id)
    if not user: raise HTTPException(401,'User unavailable')
    return Principal(user.org_id,user.id,user.role,user.name)

def require_roles(*roles):
    def check(actor: Principal=Depends(principal)):
        if actor.role not in roles: raise HTTPException(403,'Role does not permit this action')
        return actor
    return check
writer=require_roles('owner','controller','analyst')
controller=require_roles('owner','controller')
owner=require_roles('owner')

def scoped(db, model, identifier, actor):
    row=db.scalar(select(model).where(model.id==identifier,model.org_id==actor.org_id))
    if not row: raise HTTPException(404,'Record not found')
    return row

def issue_session(db,user):
    token=secrets.token_urlsafe(48)
    db.add(AuthSession(token_hash=digest(token),user_id=user.id,expires_at=datetime.now(timezone.utc)+timedelta(hours=8)))
    db.commit()
    return {'token':token,'user':{'id':user.id,'org_id':user.org_id,'name':user.name,'role':user.role,'email':user.email}}

_lock=threading.Lock()
_attempts={}
def login_limit(request,slug):
    key=(request.client.host if request.client else 'local',slug)
    now=time.monotonic()
    with _lock:
        expired=[k for k,v in _attempts.items() if not v or now-v[-1]>60]
        for k in expired: _attempts.pop(k,None)
        values=[t for t in _attempts.get(key,[]) if now-t<60]
        if len(values)>=10: raise HTTPException(429,'Too many attempts; retry in one minute')
        _attempts[key]=values+[now]
