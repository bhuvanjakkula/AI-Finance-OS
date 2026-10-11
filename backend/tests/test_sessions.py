from datetime import timedelta
from test_platform import workspace, member
from app.auth import digest
from app.database import SessionLocal
from app.platform_models import AuthSession, now


def test_session_identifiers_revocation_and_user_isolation(workspace):
    c,h,_,_,slug=workspace
    second=c.post('/auth/login',json={'slug':slug,'email':'owner@example.com','password':'Correct-horse-1234'}).json()['token']
    other_headers={'Authorization':'Bearer '+second}
    sessions=c.get('/auth/sessions',headers=h).json()
    assert len(sessions)==2
    assert sum(s['current'] for s in sessions)==1
    assert all(s['id'] not in (digest(second),digest(h['Authorization'][7:])) for s in sessions)
    auditor,_=member(c,h,slug,'auditor')
    foreign=c.get('/auth/sessions',headers=auditor).json()[0]['id']
    assert c.post('/auth/sessions/'+foreign+'/revoke',headers=h).status_code==404
    target=next(s['id'] for s in sessions if not s['current'])
    assert c.post('/auth/sessions/'+target+'/revoke',headers=h).status_code==200
    assert c.get('/auth/me',headers=other_headers).status_code==401
    assert c.get('/auth/me',headers=h).status_code==200
    assert c.get('/auth/me',headers=auditor).status_code==200
    assert c.post('/auth/sessions/'+target+'/revoke',headers=h).status_code==404
    assert c.get('/auth/sessions').status_code==401
    events=c.get('/audit/events',headers=h).json()
    assert any(e['action']=='session_revoked' for e in events)


def test_revoke_others_preserves_current_and_filters_expiry(workspace):
    c,h,_,user,slug=workspace
    second=c.post('/auth/login',json={'slug':slug,'email':'owner@example.com','password':'Correct-horse-1234'}).json()['token']
    auditor,_=member(c,h,slug,'auditor')
    with SessionLocal() as db:
        db.add(AuthSession(token_hash=digest('expired-test-token'),user_id=user['id'],expires_at=now()-timedelta(hours=1)))
        db.commit()
    sessions=c.get('/auth/sessions',headers=h).json()
    assert len(sessions)==2
    result=c.post('/auth/sessions/revoke-others',headers=h)
    assert result.status_code==200,result.text
    assert result.json()['revoked_count']==2
    assert c.get('/auth/me',headers={'Authorization':'Bearer '+second}).status_code==401
    assert c.get('/auth/me',headers=auditor).status_code==200
    current=c.get('/auth/sessions',headers=h).json()
    assert len(current)==1 and current[0]['current']
    assert c.post('/auth/sessions/revoke-others',headers=h).json()['revoked_count']==0
    assert c.post('/auth/sessions/revoke-others').status_code==401
