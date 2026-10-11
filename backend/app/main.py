"""AI Finance OS platform API: authenticated scope, deterministic finance, controlled actions."""
import csv, io, json, os, re, hashlib, zipfile
import httpx
from contextlib import asynccontextmanager
from datetime import date, timedelta, timezone
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .security_controls import SecurityHeaders, validate_production
from .pqc_security import keys as security_keys, sign_receipt
from fastapi.responses import Response, JSONResponse
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from .database import Base, engine
from .platform_models import *
from .auth import *
from .contracts import *
from . import finance_engine as finance
from . import agents
from . import event_pipeline
from . import anti_entropy
from . import close_readiness
from . import cash_review
from . import treasury_stress
from . import collections
from . import liquidity_limits
from . import executive_briefing
from .erp import CONNECTORS, ConnectorError

@asynccontextmanager
async def lifespan(app):
    validate_production()
    security_keys()
    if os.getenv('FINANCE_AUTO_CREATE','true').lower()=='true': Base.metadata.create_all(engine)
    yield
app=FastAPI(title='AI Finance OS Platform',version='0.6.1',lifespan=lifespan,docs_url=None if os.getenv('FINANCE_ENV')=='production' else '/docs',redoc_url=None if os.getenv('FINANCE_ENV')=='production' else '/redoc',openapi_url=None if os.getenv('FINANCE_ENV')=='production' else '/openapi.json')
_cors_raw = os.getenv('CORS_ORIGINS', '*')
_allowed_origins = ['*'] if _cors_raw == '*' else [o.strip() for o in _cors_raw.split(',') if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_allowed_origins, allow_methods=['*'], allow_headers=['*'], allow_credentials=False if '*' in _allowed_origins else True)
app.add_middleware(SecurityHeaders)
_hosts_raw = os.getenv('FINANCE_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver')
_allowed_hosts = ['*'] if _hosts_raw == '*' else [h.strip() for h in _hosts_raw.split(',') if h.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

@app.post('/integration/events',status_code=202)
def receive_event(body:IntegrationInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    result=event_pipeline.receive(db,actor,body);db.commit();return result

@app.post('/integration/process')
def process_events(actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    result=event_pipeline.process(db,actor);db.commit();return result

@app.get('/integration/status')
def integration_status(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return {**event_pipeline.monitor(db,actor),'freshness':anti_entropy.freshness(db,actor)}

@app.get('/integration/policy')
def reconciliation_policy(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return anti_entropy.policy(db,actor)

@app.post('/integration/policy')
def configure_reconciliation(body:ReconciliationPolicyInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    result=anti_entropy.update_policy(db,actor,body);db.commit();return result

@app.get('/integration/manifest')
def export_manifest(entity_id:str,connection_id:str='manual',actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return anti_entropy.local_manifest(db,actor,entity_id,connection_id)

@app.post('/integration/reconcile')
def reconcile_manifest(body:SourceManifest,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    result=anti_entropy.compare(db,actor,body);db.commit();return result

@app.post('/integration/events/{message_id}/retry')
def retry_event(message_id:str,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    event_pipeline.lock(db,actor)
    row=scoped(db,IntegrationMessage,message_id,actor)
    if row.status not in ('failed','dead_letter'): raise HTTPException(409,'Only validation failures can be retried; conflicts require source arbitration')
    row.status='queued';row.attempts=0;row.error=''
    finance.audit(db,actor,'integration_retry_requested',row.id);db.commit();return {'id':row.id,'status':row.status}

@app.get('/integration/outbox')
def integration_outbox(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':r.id,'message_id':r.message_id,'payload':r.payload,'created_at':r.created_at} for r in db.scalars(select(IntegrationOutbox).where(IntegrationOutbox.org_id==actor.org_id).order_by(IntegrationOutbox.created_at.desc()).limit(500)).all()]

@app.exception_handler(IntegrityError)
async def conflict_handler(request,error):
    return JSONResponse(status_code=409,content={'detail':'Record conflicts with an existing organization, account or source reference'})

@app.get('/health')
def health(): return {'status':'ok','version':app.version,'mode':'authenticated_platform'}

@app.post('/auth/register',status_code=201)
def register(body:Register,db:Session=Depends(db_session)):
    if os.getenv('ALLOW_REGISTRATION','false' if os.getenv('FINANCE_ENV')=='production' else 'true').lower()!='true': raise HTTPException(403,'Organization registration is disabled')
    organization=Organization(id=uid(),slug=body.slug,name=body.organization);db.add(organization);db.flush()
    user=User(id=uid(),org_id=organization.id,email=body.email.lower(),name=body.name,role='owner',password_hash=password_hash(body.password.get_secret_value()));db.add(user);db.flush()
    actor=Principal(organization.id,user.id,user.role,user.name)
    finance.audit(db,actor,'organization_created',organization.id)
    return issue_session(db,user)

@app.post('/auth/local-owner')
def local_owner_access(request:Request,db:Session=Depends(db_session)):
    from urllib.parse import urlsplit
    if os.getenv('FINANCE_ENV')=='production' or os.getenv('FINANCE_LOCAL_OWNER_ACCESS','false').lower()!='true': raise HTTPException(403,'Local owner access disabled')
    if not request.client or request.client.host not in ('127.0.0.1','::1'): raise HTTPException(403,'Loopback access required')
    origin=request.headers.get('origin')
    if origin and urlsplit(origin).hostname not in ('127.0.0.1','localhost','::1'): raise HTTPException(403,'Local origin required')
    if request.headers.get('sec-fetch-site')=='cross-site': raise HTTPException(403,'Cross-site request rejected')
    email=os.getenv('FINANCE_LOCAL_OWNER_EMAIL','').strip().lower()
    slug=os.getenv('FINANCE_LOCAL_OWNER_ORG','').strip()
    if not email or not slug: raise HTTPException(503,'Configure local owner identity')
    org=db.scalar(select(Organization).where(Organization.slug==slug))
    if org is None:
        org=Organization(id=uid(),slug=slug,name='Bhuvan Finance Workspace');db.add(org);db.flush()
    user=db.scalar(select(User).where(User.org_id==org.id,User.email==email))
    if user is None:
        import secrets
        user=User(id=uid(),org_id=org.id,email=email,name='Bhuvan Jakkula',role='owner',password_hash=password_hash(secrets.token_urlsafe(48)));db.add(user);db.flush()
    if user.role!='owner': raise HTTPException(403,'Configured account is not an owner')
    finance.audit(db,Principal(org.id,user.id,user.role,user.name),'local_owner_signed_in',user.id)
    return issue_session(db,user)

@app.post('/auth/login')
def login(body:Login,request:Request,db:Session=Depends(db_session)):
    login_limit(request,body.slug)
    org=db.scalar(select(Organization).where(Organization.slug==body.slug))
    user=db.scalar(select(User).where(User.org_id==org.id,User.email==body.email.lower())) if org else None
    if not user or not verify_password(body.password.get_secret_value(),user.password_hash): raise HTTPException(401,'Invalid organization or credentials')
    finance.audit(db,Principal(user.org_id,user.id,user.role,user.name),'user_signed_in',user.id)
    return issue_session(db,user)

@app.get('/auth/me')
def me(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    organization=db.get(Organization,actor.org_id)
    return {'id':actor.user_id,'org_id':actor.org_id,'name':actor.name,'role':actor.role,'organization':organization.name,'slug':organization.slug}

@app.post('/auth/logout')
def logout(authorization:str=Header(default=''),actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    session=db.get(AuthSession,digest(authorization[7:]));db.delete(session);finance.audit(db,actor,'user_signed_out',actor.user_id);db.commit();return {'signed_out':True}

@app.get('/auth/sessions')
def my_sessions(authorization:str=Header(default=''),actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    current=digest(authorization[7:])
    return [{'id':session_identifier(s.token_hash),'expires_at':s.expires_at.replace(tzinfo=timezone.utc).isoformat(),'current':s.token_hash==current} for s in db.scalars(select(AuthSession).where(AuthSession.user_id==actor.user_id,AuthSession.expires_at>now()).order_by(AuthSession.expires_at.desc())).all()]

@app.post('/auth/sessions/revoke-others')
def revoke_other_sessions(authorization:str=Header(default=''),actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    current=digest(authorization[7:])
    rows=db.scalars(select(AuthSession).where(AuthSession.user_id==actor.user_id,AuthSession.token_hash!=current)).all()
    for row in rows: db.delete(row)
    finance.audit(db,actor,'other_sessions_revoked',actor.user_id,{'count':len(rows)})
    db.commit();return {'revoked_count':len(rows),'current_session_preserved':True}

@app.get('/security/status')
def security_status(actor:Principal=Depends(owner)):
    loaded=security_keys()
    return {'environment':os.getenv('FINANCE_ENV','development'),'encrypted_payload_storage':bool(loaded),'audit_signature':'ML-DSA-65' if loaded else 'not_configured','storage_suite':'ML-KEM-768/HKDF-SHA256/AES-256-GCM/v1' if loaded else 'not_configured','scope':'JSON payloads and evidence; indexed scalar columns require disk/database encryption','transport':'Negotiated TLS must be verified at deployment gateway','independent_security_review':'pending'}

@app.post('/auth/sessions/{session_id}/revoke')
def revoke_session(session_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    row=next((s for s in db.scalars(select(AuthSession).where(AuthSession.user_id==actor.user_id)).all() if session_identifier(s.token_hash)==session_id),None)
    if not row: raise HTTPException(404,'Session not found')
    db.delete(row);finance.audit(db,actor,'session_revoked',actor.user_id,{'session_id':session_id});db.commit();return {'revoked':True}

@app.get('/users')
def users(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':u.id,'name':u.name,'email':u.email,'role':u.role} for u in db.scalars(select(User).where(User.org_id==actor.org_id)).all()]

@app.post('/users',status_code=201)
def create_user(body:Member,actor:Principal=Depends(owner),db:Session=Depends(db_session)):
    user=User(id=uid(),org_id=actor.org_id,name=body.name,email=body.email.lower(),role=body.role,password_hash=password_hash(body.password.get_secret_value()));db.add(user)
    finance.audit(db,actor,'member_created',user.id,{'role':user.role});db.commit();return {'id':user.id}

@app.get('/entities')
def entities(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':e.id,'code':e.code,'name':e.name,'currency':e.currency,'parent_id':e.parent_id} for e in db.scalars(select(LegalEntity).where(LegalEntity.org_id==actor.org_id)).all()]

@app.post('/entities',status_code=201)
def create_entity(body:EntityInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    if body.parent_id: scoped(db,LegalEntity,body.parent_id,actor)
    entity=LegalEntity(id=uid(),org_id=actor.org_id,**body.model_dump());db.add(entity)
    finance.audit(db,actor,'entity_created',entity.id);db.commit();return {'id':entity.id}

@app.get('/entities/{entity_id}/accounts')
def accounts(entity_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor)
    return [{'id':a.id,'code':a.code,'name':a.name,'category':a.category,'group_code':a.group_code,'is_cash':a.is_cash} for a in db.scalars(select(Account).where(Account.org_id==actor.org_id,Account.entity_id==entity_id)).all()]

@app.post('/entities/{entity_id}/accounts',status_code=201)
def create_account(entity_id:str,body:AccountInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor)
    if body.is_cash and body.category!='asset': raise HTTPException(422,'Cash accounts must be assets')
    account=Account(id=uid(),org_id=actor.org_id,entity_id=entity_id,**body.model_dump());db.add(account)
    finance.audit(db,actor,'account_mapping_created',account.id,body.model_dump());db.commit();return {'id':account.id}

@app.post('/journals/import')
def import_journals(body:JournalBatch,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    if body.connection_id not in ('manual','csv','legacy-csv'):
        scoped(db,ERPConnection,body.connection_id,actor)
    result=finance.ingest_journals(db,actor,body.entity_id,body.connection_id,body.journals);db.commit();return result

@app.get('/journals')
def journals(entity_id:str,include_history:bool=False,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor)
    rows=db.scalars(select(Journal).where(Journal.org_id==actor.org_id,Journal.entity_id==entity_id)).all() if include_history else finance.active_journals(db,actor.org_id,entity_id)
    return [finance.journal_dict(db,j) for j in rows]

@app.get('/journals/{journal_id}/lineage')
def lineage(journal_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    journal=scoped(db,Journal,journal_id,actor);source=scoped(db,SourceRecord,journal.source_id,actor)
    evidence=db.scalars(select(Evidence).where(Evidence.org_id==actor.org_id,Evidence.journal_id==journal_id)).all()
    return {'journal':finance.journal_dict(db,journal),'source':{'id':source.id,'connection_id':source.connection_id,'payload':source.payload,'sha256':source.payload_hash,'hash_valid':finance.hash_json(source.payload)==source.payload_hash},'evidence':[{'id':e.id,'filename':e.filename,'sha256':e.content_hash,'hash_valid':hashlib.sha256(e.content).hexdigest()==e.content_hash} for e in evidence]}

@app.get('/reports/trial-balance')
def trial_balance(entity_id:str,period:str|None=None,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    entity=scoped(db,LegalEntity,entity_id,actor);start,end=finance.period_dates(period) if period else (None,None)
    return {'currency':entity.currency,'rows':finance.trial_balance(db,actor.org_id,entity_id,start,end)}

@app.get('/reports/statements')
def statements(entity_id:str,period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    entity=scoped(db,LegalEntity,entity_id,actor)
    return {'currency':entity.currency,**finance.statements(db,actor.org_id,entity_id,period)}

@app.get('/reports/variance')
def variance(entity_id:str,period:str,previous_period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor)
    now_report=finance.statements(db,actor.org_id,entity_id,period);before=finance.statements(db,actor.org_id,entity_id,previous_period)
    return {'current':period,'previous':previous_period,'metrics':[{ 'metric':key,'current':now_report[key],'previous':before[key],'variance':finance.amount(Decimal(now_report[key])-Decimal(before[key]))} for key in ('revenue','expenses','net_income')]}

@app.get('/reports/export.csv')
def export_csv(entity_id:str,period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor);start,end=finance.period_dates(period)
    output=io.StringIO();writer_csv=csv.DictWriter(output,fieldnames=['code','name','category','group_code','debit','credit','balance']);writer_csv.writeheader()
    for row in finance.trial_balance(db,actor.org_id,entity_id,start,end):
        values={k:row[k] for k in writer_csv.fieldnames}
        for key in ('code','name','group_code'):
            if values[key].lstrip().startswith(('=','+','-','@')): values[key]="'"+values[key]
        writer_csv.writerow(values)
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="trial-balance.csv"'})

@app.get('/integrity/findings')
def findings(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':f.id,'journal_id':f.journal_id,'rule':f.rule,'severity':f.severity,'detail':f.detail,'status':f.status} for f in db.scalars(select(Finding).where(Finding.org_id==actor.org_id)).all()]

@app.post('/integrity/findings/{finding_id}/review')
def review_finding(finding_id:str,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    finding=scoped(db,Finding,finding_id,actor);finding.status='reviewed';finance.audit(db,actor,'finding_reviewed',finding.id);db.commit();return {'status':'reviewed'}

@app.get('/agents/status')
def ai_status(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    count=db.scalar(select(func.count()).select_from(AnalysisRun).where(AnalysisRun.org_id==actor.org_id,AnalysisRun.kind=='investigation',AnalysisRun.created_at>=now()-timedelta(days=1)))
    return {'provider':'OpenAI Responses API','configured':bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')),'model':os.getenv('OPENAI_MODEL') or None,'daily_run_limit':int(os.getenv('AI_DAILY_RUN_LIMIT','100')),'completed_investigations_today':count,'output_token_limit':1200,'external_data_scope':'Selected journal, finding details and supporting document metadata are sent to OpenAI. Documents themselves are not uploaded.','execution_scope':'Recommendations only; no posting, approval or trading tools.','storage':'Requests set store=false; this alone is not a zero-data-retention guarantee.'}

@app.post('/agents/investigate')
def agent_run(body:AgentInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    finding=scoped(db,Finding,body.finding_id,actor)
    count=db.scalar(select(func.count()).select_from(AnalysisRun).where(AnalysisRun.org_id==actor.org_id,AnalysisRun.kind=='investigation',AnalysisRun.created_at>=now()-timedelta(days=1)))
    if count>=int(os.getenv('AI_DAILY_RUN_LIMIT','100')): raise HTTPException(429,'Daily investigation run limit reached')
    try: output,usage=agents.investigate(db,actor,finding,body.provider)
    except (ValueError,httpx.HTTPError) as exc: raise HTTPException(502,str(exc) if isinstance(exc,ValueError) else 'AI provider unavailable')
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='investigation',inputs=body.model_dump(),output={'recommendation':output,'usage':usage});db.add(run)
    finance.audit(db,actor,'investigation_recorded',run.id,{'provider':body.provider,'model':usage['model'],'evidence_ids':output['evidence_ids']});db.commit();return {'id':run.id,**run.output}

@app.get('/runs')
def runs(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':r.id,'kind':r.kind,'created_at':r.created_at.isoformat(),'inputs':{k:v for k,v in r.inputs.items() if k!='source_csv'},'output':r.output} for r in db.scalars(select(AnalysisRun).where(AnalysisRun.org_id==actor.org_id).order_by(AnalysisRun.created_at.desc()).limit(100)).all()]

@app.get('/close/period-control')
def period_control_status(entity_id:str,period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor);finance.period_dates(period)
    row=db.scalar(select(PeriodControl).where(PeriodControl.org_id==actor.org_id,PeriodControl.entity_id==entity_id,PeriodControl.period==period))
    return {'status':row.status if row else 'open','submitted_by':row.submitted_by if row else None,'reviewed_by':row.reviewed_by if row else None,'note':row.note if row else ''}

@app.post('/close/period-control')
def period_control_action(body:PeriodActionInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,body.entity_id,actor)
    db.scalar(select(Organization).where(Organization.id==actor.org_id).with_for_update())
    row=db.scalar(select(PeriodControl).where(PeriodControl.org_id==actor.org_id,PeriodControl.entity_id==body.entity_id,PeriodControl.period==body.period))
    if row is None:
        row=PeriodControl(id=uid(),org_id=actor.org_id,entity_id=body.entity_id,period=body.period,status='open',note='');db.add(row);db.flush()
    if body.action=='submit':
        if row.status!='open': raise HTTPException(409,'Period must be open')
        if not close_readiness.assess(db,actor,body.entity_id,body.period)['ready_for_review']: raise HTTPException(409,'Resolve readiness blockers before submitting')
        row.status='review';row.submitted_by=actor.user_id;row.reviewed_by=None
    elif body.action in ('approve','reject'):
        if row.status!='review': raise HTTPException(409,'Period must be in review')
        if row.submitted_by==actor.user_id: raise HTTPException(403,'A different controller must decide')
        if body.action=='approve' and not close_readiness.assess(db,actor,body.entity_id,body.period)['ready_for_review']: raise HTTPException(409,'Readiness changed; resolve blockers')
        row.status='locked' if body.action=='approve' else 'open';row.reviewed_by=actor.user_id
    else:
        if actor.role!='owner': raise HTTPException(403,'Only an owner may reopen a period')
        if row.status=='open': raise HTTPException(409,'Period is already open')
        row.status='open'
    row.note=body.note
    finance.audit(db,actor,'period_'+body.action,row.id,body.model_dump());db.commit()
    return period_control_status(body.entity_id,body.period,actor,db)

@app.get('/close/readiness')
def close_status(entity_id:str,period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return close_readiness.assess(db,actor,entity_id,period)

@app.post('/close/readiness',status_code=201)
def save_close_status(body:CloseReadinessInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    output=close_readiness.assess(db,actor,body.entity_id,body.period)
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='close_readiness',inputs=body.model_dump(),output=output)
    db.add(run);finance.audit(db,actor,'close.readiness',run.id,{'entity_id':body.entity_id,'period':body.period,'blockers':output['blockers']});db.commit()
    return {'run_id':run.id,**output}

@app.get('/close/snapshots')
def close_snapshots(entity_id:str,period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor);finance.period_dates(period)
    records=db.scalars(select(AnalysisRun).where(AnalysisRun.org_id==actor.org_id,AnalysisRun.kind=='close_readiness').order_by(AnalysisRun.created_at.desc(),AnalysisRun.id.desc())).all()
    selected=[r for r in records if r.inputs.get('entity_id')==entity_id and r.inputs.get('period')==period][:100]
    return [{'id':r.id,'created_at':r.created_at.isoformat(),'actor_id':r.actor_id,'ready_for_review':r.output['ready_for_review'],'blockers':r.output['blockers'],'output':r.output} for r in selected]

@app.get('/close/snapshots/{run_id}/export')
def export_close_snapshot(run_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    run=scoped(db,AnalysisRun,run_id,actor)
    if run.kind!='close_readiness': raise HTTPException(422,'Only close-readiness snapshots can be exported here')
    if not security_keys(): raise HTTPException(503,'Initialize encryption keys before exporting signed close snapshots')
    payload={'run_id':run.id,'org_id':run.org_id,'actor_id':run.actor_id,'created_at':run.created_at.isoformat(),'inputs':run.inputs,'output':run.output}
    content=finance.canonical(payload).encode('utf-8')
    receipt=sign_receipt({'org_id':actor.org_id,'entity_id':run.inputs['entity_id'],'files_sha512':{'close-readiness.json':hashlib.sha512(content).hexdigest()},'created_at':now().isoformat()})
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('close-readiness.json',content)
        archive.writestr('pqc-receipt.json',json.dumps(receipt,indent=2))
    finance.audit(db,actor,'close.snapshot_exported',run.id,{'sha512':hashlib.sha512(content).hexdigest()});db.commit()
    return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="close-readiness.zip"'})

@app.get('/close/tasks')
def tasks(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':t.id,'entity_id':t.entity_id,'title':t.title,'owner_id':t.owner_id,'due_date':t.due_date,'period':t.period,'depends_on':t.depends_on,'status':t.status} for t in db.scalars(select(PlatformTask).where(PlatformTask.org_id==actor.org_id).order_by(PlatformTask.due_date)).all()]

@app.post('/close/tasks',status_code=201)
def create_task(body:TaskInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,body.entity_id,actor);scoped(db,User,body.owner_id,actor)
    for dependency in body.depends_on:
        previous=scoped(db,PlatformTask,dependency,actor)
        if previous.entity_id!=body.entity_id: raise HTTPException(422,'Task dependencies must belong to the same entity')
    payload=body.model_dump(mode='json');task=PlatformTask(id=uid(),org_id=actor.org_id,**payload);db.add(task)
    finance.audit(db,actor,'close_task_created',task.id,payload);db.commit();return {'id':task.id}

@app.patch('/close/tasks/{task_id}')
def update_task(task_id:str,body:TaskState,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    task=scoped(db,PlatformTask,task_id,actor)
    if actor.role=='analyst' and task.owner_id!=actor.user_id: raise HTTPException(403,'Only the task owner or controller can update this task')
    if body.status=='complete' and any(scoped(db,PlatformTask,d,actor).status!='complete' for d in task.depends_on): raise HTTPException(409,'Complete task dependencies first')
    if body.status!='complete':
        dependents=db.scalars(select(PlatformTask).where(PlatformTask.org_id==actor.org_id,PlatformTask.status=='complete')).all()
        if any(task.id in t.depends_on for t in dependents): raise HTTPException(409,'Reopen completed dependent tasks first')
    task.status=body.status;finance.audit(db,actor,'close_task_updated',task.id,body.model_dump());db.commit();return {'status':task.status}

@app.post('/proposals',status_code=201)
def create_proposal(body:ProposalInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    entity=scoped(db,LegalEntity,body.entity_id,actor);finance.validate_journal(db,actor,entity,body.journal)
    proposal=Proposal(id=uid(),org_id=actor.org_id,entity_id=entity.id,submitted_by=actor.user_id,reason=body.reason,journal_payload=body.journal.model_dump(mode='json'));db.add(proposal)
    finance.audit(db,actor,'journal_proposed',proposal.id,{'reason':body.reason});db.commit();return {'id':proposal.id}

@app.get('/proposals')
def proposals(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':p.id,'entity_id':p.entity_id,'submitted_by':p.submitted_by,'reviewed_by':p.reviewed_by,'reason':p.reason,'status':p.status,'decision_note':p.decision_note,'journal':p.journal_payload} for p in db.scalars(select(Proposal).where(Proposal.org_id==actor.org_id)).all()]

@app.post('/proposals/{proposal_id}/decision')
def decide(proposal_id:str,body:Decision,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    proposal=scoped(db,Proposal,proposal_id,actor)
    if proposal.submitted_by==actor.user_id: raise HTTPException(403,'Independent reviewer required; submitter cannot approve or reject their own proposal')
    if proposal.status!='pending': raise HTTPException(409,'Proposal already decided')
    changed=db.execute(update(Proposal).where(Proposal.id==proposal.id,Proposal.org_id==actor.org_id,Proposal.status=='pending').values(status=body.decision,reviewed_by=actor.user_id,decision_note=body.note))
    if changed.rowcount!=1: raise HTTPException(409,'Proposal was already decided by another reviewer')
    finance.audit(db,actor,'journal_proposal_decided',proposal.id,body.model_dump());db.commit();return {'status':body.decision,'posted_to_erp':False}

@app.get('/proposals/{proposal_id}/export')
def proposal_export(proposal_id:str,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    proposal=scoped(db,Proposal,proposal_id,actor)
    if proposal.status!='approved': raise HTTPException(409,'Only approved proposals can be exported')
    return {'proposal_id':proposal.id,'journal':proposal.journal_payload,'approved_by':proposal.reviewed_by,'scope':'Approved draft only; no ERP posting performed'}

@app.post('/bank/import')
def bank_import(body:BankBatch,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    entity=scoped(db,LegalEntity,body.entity_id,actor);count=0
    for row in body.transactions:
        finance.require_open_period(db,actor,body.entity_id,row.date.strftime('%Y-%m'))
        if row.currency!=entity.currency: raise HTTPException(422,'Bank currency must match entity currency')
        if not row.amount: raise HTTPException(422,'Bank amount must be nonzero')
        existing=db.scalar(select(BankTransaction).where(BankTransaction.org_id==actor.org_id,BankTransaction.entity_id==entity.id,BankTransaction.external_id==row.external_id))
        if existing:
            if existing.date!=row.date.isoformat() or existing.amount!=row.amount or existing.reference!=row.reference: raise HTTPException(409,'Conflicting bank transaction ID')
            continue
        db.add(BankTransaction(id=uid(),org_id=actor.org_id,entity_id=entity.id,**row.model_dump(mode='python',exclude={'date'}),date=row.date.isoformat()));count+=1
    finance.audit(db,actor,'bank_imported',entity.id,{'imported':count});db.commit();return {'imported':count}

@app.get('/reconciliation')
def reconciliation(entity_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor)
    journal_ids={j.id for j in finance.active_journals(db,actor.org_id,entity_id)}
    cash_accounts={a.id for a in db.scalars(select(Account).where(Account.org_id==actor.org_id,Account.entity_id==entity_id,Account.is_cash==True)).all()}
    lines=[l for l in db.scalars(select(JournalLine).where(JournalLine.org_id==actor.org_id)).all() if l.journal_id in journal_ids and l.account_id in cash_accounts]
    matches=db.scalars(select(ReconciliationMatch).where(ReconciliationMatch.org_id==actor.org_id)).all()
    active_line_ids={l.id for l in lines}
    active_matches=[m for m in matches if m.line_id in active_line_ids]
    by_bank={m.bank_id:m for m in active_matches};used={m.line_id for m in matches}
    banks=db.scalars(select(BankTransaction).where(BankTransaction.org_id==actor.org_id,BankTransaction.entity_id==entity_id)).all();result=[]
    for bank in banks:
        candidates=[]
        if bank.id not in by_bank:
            for line in lines:
                journal=db.get(Journal,line.journal_id)
                if line.id not in used and line.debit-line.credit==bank.amount and abs((date.fromisoformat(journal.posting_date)-date.fromisoformat(bank.date)).days)<=3 and bank.reference and bank.reference==line.reference:
                    candidates.append({'line_id':line.id,'journal_id':journal.id,'external_id':journal.external_id,'amount':finance.amount(line.debit-line.credit)})
        result.append({'id':bank.id,'external_id':bank.external_id,'date':bank.date,'amount':finance.amount(bank.amount),'reference':bank.reference,'status':'matched' if bank.id in by_bank else ('ambiguous' if len(candidates)>1 else 'unmatched'),'suggestions':candidates,'matched_line_id':by_bank[bank.id].line_id if bank.id in by_bank else None})
    return {'transactions':result,'unmatched_cash_lines':[{'id':l.id,'journal_id':l.journal_id,'amount':finance.amount(l.debit-l.credit),'reference':l.reference} for l in lines if l.id not in used],'rule':'Exact signed amount and reference, within three days; matches require controller confirmation'}

@app.post('/reconciliation/matches',status_code=201)
def confirm_match(body:MatchInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    bank=scoped(db,BankTransaction,body.bank_id,actor);line=scoped(db,JournalLine,body.line_id,actor);journal=scoped(db,Journal,line.journal_id,actor);account=scoped(db,Account,line.account_id,actor)
    active={j.id for j in finance.active_journals(db,actor.org_id,bank.entity_id)}
    if journal.entity_id!=bank.entity_id or journal.id not in active or not account.is_cash or journal.currency!=bank.currency or line.debit-line.credit!=bank.amount: raise HTTPException(422,'Bank and active cash ledger line must have the same entity, currency and signed amount')
    existing=db.scalar(select(ReconciliationMatch).where(ReconciliationMatch.org_id==actor.org_id,ReconciliationMatch.bank_id==bank.id))
    if existing and existing.line_id not in {l.id for l in db.scalars(select(JournalLine).where(JournalLine.journal_id.in_(active))).all()}:
        db.delete(existing);db.flush()
    match=ReconciliationMatch(id=uid(),org_id=actor.org_id,bank_id=bank.id,line_id=line.id,matched_by=actor.user_id);db.add(match)
    finance.audit(db,actor,'bank_match_confirmed',match.id,body.model_dump());db.commit();return {'id':match.id}

@app.post('/evidence',status_code=201)
async def upload_evidence(journal_id:str=Form(...),file:UploadFile=File(...),actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    scoped(db,Journal,journal_id,actor);content=await file.read(5_000_001)
    if not content or len(content)>5_000_000: raise HTTPException(413,'Evidence must contain 1 byte to 5 MB')
    filename=(file.filename or 'evidence.bin').replace('\\','/').split('/')[-1][:200]
    evidence=Evidence(id=uid(),org_id=actor.org_id,journal_id=journal_id,filename=filename,content=content,content_hash=hashlib.sha256(content).hexdigest(),uploaded_by=actor.user_id);db.add(evidence)
    finance.audit(db,actor,'evidence_uploaded',evidence.id,{'journal_id':journal_id,'sha256':evidence.content_hash});db.commit();return {'id':evidence.id,'sha256':evidence.content_hash}

@app.get('/evidence')
def evidence_list(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':e.id,'journal_id':e.journal_id,'filename':e.filename,'sha256':e.content_hash,'created_at':e.created_at.isoformat()} for e in db.scalars(select(Evidence).where(Evidence.org_id==actor.org_id)).all()]

@app.get('/evidence/{evidence_id}/download')
def evidence_download(evidence_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    e=scoped(db,Evidence,evidence_id,actor)
    return Response(e.content,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="evidence.bin"','X-Content-Type-Options':'nosniff'})

@app.get('/audit/gaps')
def audit_gaps(entity_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor);covered={e.journal_id for e in db.scalars(select(Evidence).where(Evidence.org_id==actor.org_id)).all()}
    return [{'journal_id':j.id,'external_id':j.external_id,'finding':'No uploaded document linked'} for j in finance.active_journals(db,actor.org_id,entity_id) if j.id not in covered]

@app.get('/audit/package')
def audit_package(entity_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor);journals=finance.active_journals(db,actor.org_id,entity_id);ids={j.id for j in journals}
    buffer=io.BytesIO();documents=db.scalars(select(Evidence).where(Evidence.org_id==actor.org_id)).all();manifest=[]
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for e in documents:
            if e.journal_id in ids:
                path='evidence/'+e.id+'.bin';archive.writestr(path,e.content);manifest.append({'path':path,'filename':e.filename,'sha256':e.content_hash,'journal_id':e.journal_id})
        archive.writestr('manifest.json',json.dumps(manifest,indent=2));archive.writestr('journals.json',json.dumps([finance.journal_dict(db,j) for j in journals],indent=2))
        archive.writestr('source-records.json',json.dumps([{'id':j.source_id,'payload':db.get(SourceRecord,j.source_id).payload,'sha256':db.get(SourceRecord,j.source_id).payload_hash} for j in journals],indent=2))
        archive.writestr('chain-verification.json',json.dumps(finance.verify_chain(db,actor.org_id),indent=2))
        archive.writestr('audit-events.json',json.dumps([finance.event_dict(e) for e in db.scalars(select(PlatformEvent).where(PlatformEvent.org_id==actor.org_id)).all()],indent=2))
        if security_keys():
            files={name:hashlib.sha512(archive.read(name)).hexdigest() for name in archive.namelist()}
            receipt=sign_receipt({'org_id':actor.org_id,'entity_id':entity_id,'files_sha512':files,'created_at':now().isoformat()})
            archive.writestr('pqc-receipt.json',json.dumps(receipt,indent=2))
    return Response(buffer.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="audit-evidence.zip"'})

@app.get('/audit/events')
def events(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [finance.event_dict(e) for e in db.scalars(select(PlatformEvent).where(PlatformEvent.org_id==actor.org_id).order_by(PlatformEvent.id.desc()).limit(200)).all()]

@app.get('/audit/verify')
def verify_audit(actor:Principal=Depends(principal),db:Session=Depends(db_session)): return finance.verify_chain(db,actor.org_id)

@app.post('/cash/payments',status_code=201)
def create_payment(body:PaymentInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,body.entity_id,actor);payment=PaymentSchedule(id=uid(),org_id=actor.org_id,**body.model_dump(mode='python',exclude={'due_date'}),due_date=body.due_date.isoformat());db.add(payment)
    finance.audit(db,actor,'payment_schedule_created',payment.id,body.model_dump(mode='json'));db.commit();return {'id':payment.id}

@app.get('/cash/payments')
def payments(entity_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor)
    return [{'id':p.id,'reference':p.reference,'due_date':p.due_date,'amount':finance.amount(p.amount),'direction':p.direction} for p in db.scalars(select(PaymentSchedule).where(PaymentSchedule.org_id==actor.org_id,PaymentSchedule.entity_id==entity_id)).all()]

@app.post('/cash/forecast')
def forecast(body:ForecastInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    output=finance.cash_forecast(db,actor,body);run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='cash_forecast',inputs=body.model_dump(mode='json'),output=output);db.add(run)
    finance.audit(db,actor,'cash_forecast_created',run.id);db.commit();return {'id':run.id,**output}

@app.get('/cash/forecasts/{run_id}/review')
def review_forecast(run_id:str,as_of:date,tolerance:Decimal=Query(default=Decimal('100'),ge=0,le=Decimal('1000000000'),decimal_places=2,allow_inf_nan=False),actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return cash_review.review(db,actor,run_id,as_of,tolerance)

@app.post('/cash/stress',status_code=201)
def stress_treasury(body:TreasuryStressInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    output=treasury_stress.assess(db,actor,body)
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='treasury_stress',inputs=body.model_dump(mode='json'),output=output)
    db.add(run);finance.audit(db,actor,'treasury_stress_created',run.id,{'source_forecast_id':body.forecast_id});db.commit()
    return {'id':run.id,**output}

@app.get('/cash/collections')
def collection_monitor(entity_id:str,as_of:date,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return collections.assess(db,actor,entity_id,as_of)

@app.get('/executive/briefing')
def executive_review(period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return executive_briefing.build(db,actor,period)

@app.post('/cash/liquidity-limits',status_code=201)
def reverse_liquidity_stress(body:LiquidityLimitInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    output=liquidity_limits.assess(db,actor,body)
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='liquidity_limits',inputs=body.model_dump(mode='json'),output=output)
    db.add(run);finance.audit(db,actor,'liquidity_limits_created',run.id,{'source_forecast_id':body.forecast_id});db.commit()
    return {'id':run.id,**output}

@app.post('/consolidation/runs')
def consolidation(body:ConsolidationInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    output=finance.consolidate(db,actor,body);run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='group_trial_balance',inputs=body.model_dump(mode='json'),output=output);db.add(run)
    finance.audit(db,actor,'group_trial_balance_created',run.id);db.commit();return {'id':run.id,**output}

@app.post('/legacy/preview')
async def legacy_preview(entity_id:str=Form(...),mapping:str=Form('{}'),file:UploadFile=File(...),actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    entity=scoped(db,LegalEntity,entity_id,actor);raw=await file.read(2_000_001)
    if len(raw)>2_000_000: raise HTTPException(413,'CSV exceeds 2 MB')
    try: field_map=json.loads(mapping);reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    except (ValueError,UnicodeError): raise HTTPException(422,'Use UTF-8 CSV and a JSON field mapping')
    if not isinstance(field_map,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in field_map.items()): raise HTTPException(422,'Mapping must be an object of canonical field to CSV column')
    fields=reader.fieldnames or []
    aliases={'external_id':['external_id','journal_id','document_no','voucher_no'],'posting_date':['posting_date','date','postingDate'],'transaction_date':['transaction_date','document_date','transactionDate'],'account_code':['account_code','account','accountNumber'],'debit':['debit','dr'],'credit':['credit','cr'],'reference':['reference','document_no'],'description':['description','memo'],'version':['version']}
    suggested={k:next((c for c in candidates if c in fields),None) for k,candidates in aliases.items()}
    selected={**{k:v for k,v in suggested.items() if v},**field_map}
    required={'external_id','posting_date','account_code','debit','credit'}
    if not required.issubset(selected) or any(v not in fields for v in selected.values()):
        return {'valid':False,'columns':fields,'suggested_mapping':suggested,'errors':['Map journal reference, date, account code, debit and credit to existing CSV columns'],'journals':[]}
    groups={};errors=[]
    for number,row in enumerate(reader,2):
        if number>10001: raise HTTPException(413,'CSV exceeds 10,000 rows')
        reference=row.get(selected['external_id'],'')
        if not reference: errors.append(f'Row {number}: missing journal reference');continue
        group=groups.setdefault(reference,{'external_id':reference,'posting_date':row.get(selected['posting_date'],''),'transaction_date':row.get(selected.get('transaction_date',''),'') or row.get(selected['posting_date'],''),'currency':entity.currency,'description':row.get(selected.get('description',''),'') or '', 'version':row.get(selected.get('version',''),'1') or '1','lines':[]})
        if group['posting_date']!=row.get(selected['posting_date']): errors.append(f'Row {number}: inconsistent posting date in journal {reference}')
        group['lines'].append({'account_code':row.get(selected['account_code'],''),'debit':row.get(selected['debit'],'0') or '0','credit':row.get(selected['credit'],'0') or '0','reference':row.get(selected.get('reference',''),'') or ''})
    normalized=[]
    for payload in groups.values():
        try:
            journal=JournalInput.model_validate(payload);finance.validate_journal(db,actor,entity,journal);normalized.append(journal.model_dump(mode='json'))
        except (ValueError,HTTPException) as exc: errors.append(payload['external_id']+': '+(str(exc.detail) if isinstance(exc,HTTPException) else str(exc)))
    return {'valid':bool(normalized) and not errors,'columns':fields,'suggested_mapping':suggested,'selected_mapping':selected,'errors':errors[:100],'journals':normalized,'source_sha256':hashlib.sha256(raw).hexdigest(),'transform_version':'csv-mapping-v1','notice':'Preview only. Import these validated journals through /journals/import; keep the original extract.'}

@app.post('/connections',status_code=201)
def create_connection(body:ConnectionInput,actor:Principal=Depends(owner),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,body.entity_id,actor)
    prefix='FINANCE_SECRET_'+actor.org_id.replace('-','').upper()+'_'
    if not body.credential_env.startswith(prefix): raise HTTPException(422,'Use an organization-specific credential variable starting with '+prefix)
    allowed={'business_central':{'tenant_id','company_id','environment','account_mapping'},'netsuite':{'account_id','query_env','account_mapping'}}[body.provider]
    if set(body.config)-allowed: raise HTTPException(422,'Unsupported connector configuration field; credentials belong only in environment variables')
    if body.provider=='netsuite' and not re.fullmatch(r'FINANCE_QUERY_[A-Z0-9_]+',body.config.get('query_env','')): raise HTTPException(422,'NetSuite requires a FINANCE_QUERY_* deployment variable')
    try:
        adapter=CONNECTORS[body.provider](body.config,'not-a-real-secret');adapter.close()
    except ConnectorError as exc: raise HTTPException(422,str(exc))
    connection=ERPConnection(id=uid(),org_id=actor.org_id,**body.model_dump());db.add(connection)
    finance.audit(db,actor,'erp_connection_configured',connection.id,{'provider':body.provider});db.commit();return {'id':connection.id}

@app.get('/connections')
def connections(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':c.id,'entity_id':c.entity_id,'name':c.name,'provider':c.provider,'status':c.status,'credential_env':c.credential_env,'credentials_configured':bool(os.getenv(c.credential_env)),'config':c.config,'cursor':c.cursor} for c in db.scalars(select(ERPConnection).where(ERPConnection.org_id==actor.org_id)).all()]

@app.post('/connections/{connection_id}/sync',status_code=202)
def queue_sync(connection_id:str,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    connection=scoped(db,ERPConnection,connection_id,actor)
    pending=db.scalar(select(SyncJob).where(SyncJob.org_id==actor.org_id,SyncJob.connection_id==connection_id,SyncJob.status.in_(['queued','running'])))
    if pending: raise HTTPException(409,'An active sync already exists for this connection')
    job=SyncJob(id=uid(),org_id=actor.org_id,connection_id=connection_id,result={'actor_id':actor.user_id,'raw_rows':[]});db.add(job);connection.status='queued'
    finance.audit(db,actor,'sync_queued',job.id);db.commit();return {'id':job.id}

@app.get('/sync/jobs')
def sync_jobs(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':j.id,'connection_id':j.connection_id,'status':j.status,'attempts':j.attempts,'checkpoint':j.checkpoint,'result':{k:v for k,v in j.result.items() if k!='raw_rows'},'staged_rows':len(j.result.get('raw_rows',[]))} for j in db.scalars(select(SyncJob).where(SyncJob.org_id==actor.org_id).order_by(SyncJob.created_at.desc())).all()]

@app.post('/sync/jobs/{job_id}/step')
def sync_step(job_id:str,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    job=scoped(db,SyncJob,job_id,actor)
    if job.status not in ('queued','running','failed'): raise HTTPException(409,'Job is finished or dead-lettered')
    if job.attempts>=3: job.status='dead_letter';db.commit();return {'status':'dead_letter'}
    connection=scoped(db,ERPConnection,job.connection_id,actor);entity=scoped(db,LegalEntity,connection.entity_id,actor)
    secret=os.getenv(connection.credential_env)
    adapter=None
    try:
        if not secret: raise ConnectorError('Credential environment variable is not configured')
        adapter=CONNECTORS[connection.provider](connection.config,secret)
        page=adapter.fetch_page(job.checkpoint);rows=job.result.get('raw_rows',[])+page['rows']
        if len(rows)>100000: raise ConnectorError('Sync exceeds 100,000 staged rows; use a narrower historical extract')
        if page['cursor']==job.checkpoint and page['cursor'] is not None: raise ConnectorError('Provider pagination did not advance')
        if page['cursor']:
            job.result={**job.result,'raw_rows':rows};job.checkpoint=page['cursor'];job.status='running';connection.cursor=job.checkpoint;connection.status='syncing';db.commit()
            return {'status':'running','staged_rows':len(rows),'checkpoint':job.checkpoint}
        payloads=adapter.normalize(rows,entity.currency)
        normalized=[]
        for payload in payloads:
            latest=db.scalar(select(SourceRecord).where(SourceRecord.org_id==actor.org_id,SourceRecord.entity_id==entity.id,SourceRecord.connection_id==connection.id,SourceRecord.external_id==payload['external_id']).order_by(SourceRecord.version.desc()).limit(1))
            if latest:
                payload['version']=latest.version
                candidate=JournalInput.model_validate(payload)
                if finance.hash_json(finance.normalized_payload(candidate))!=latest.payload_hash: payload['version']=latest.version+1
            normalized.append(JournalInput.model_validate(payload))
        result=finance.ingest_journals(db,actor,entity.id,connection.id,normalized)
        job.status='complete';job.checkpoint=None;job.result={**job.result,**result,'raw_rows':rows,'raw_sha256':finance.hash_json(rows),'transform_version':connection.provider+'-v1'};connection.status='healthy';connection.cursor=None
        finance.audit(db,actor,'sync_completed',job.id,{'imported':result['imported'],'source_rows':len(rows)});db.commit();return {'status':'complete',**result}
    except (ConnectorError,ValueError,KeyError,HTTPException) as exc:
        db.rollback();job=scoped(db,SyncJob,job_id,actor);connection=scoped(db,ERPConnection,job.connection_id,actor)
        job.attempts+=1;job.status='dead_letter' if job.attempts>=3 else 'failed';connection.status='failed'
        detail=str(exc.detail) if isinstance(exc,HTTPException) else (str(exc) if isinstance(exc,ConnectorError) else 'Source normalization failed; verify required fields and financial mappings')
        job.result={**job.result,'error':detail};finance.audit(db,actor,'sync_failed',job.id,{'attempt':job.attempts,'error':detail});db.commit();return {'status':job.status,'error':detail,'attempts':job.attempts}
    finally:
        if adapter: adapter.close()

@app.get('/dashboard')
def dashboard(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    journals=finance.active_journals(db,actor.org_id);tasks=db.scalars(select(PlatformTask).where(PlatformTask.org_id==actor.org_id)).all()
    return {'organization':db.get(Organization,actor.org_id).name,'entities':db.scalar(select(func.count()).select_from(LegalEntity).where(LegalEntity.org_id==actor.org_id)),'active_journals':len(journals),'open_findings':db.scalar(select(func.count()).select_from(Finding).where(Finding.org_id==actor.org_id,Finding.status=='open')),'pending_approvals':db.scalar(select(func.count()).select_from(Proposal).where(Proposal.org_id==actor.org_id,Proposal.status=='pending')),'close_complete':sum(t.status=='complete' for t in tasks),'close_total':len(tasks),'evidence_documents':db.scalar(select(func.count()).select_from(Evidence).where(Evidence.org_id==actor.org_id)),'capabilities':[{'module':name,'scope':scope} for name,scope in [('Financial Close','Dependencies, exact bank matching, independent approvals'),('ERP Integration','Read-only adapters, staged sync, retry and dead-letter states'),('Financial Reporting','Mapped P&L, balance sheet, trial balance, variance, CSV export'),('Audit Automation','Document hashes, evidence gaps, packages, hash chain'),('Cash Intelligence','13-week payment schedules and scenarios'),('Data Accuracy','Balanced journals, mappings, duplicates, source revisions'),('Legacy Modernization','CSV schema discovery and mapping preview'),('Consolidation','Entity hierarchy, group accounts and supplied FX trial-balance preview')]]}

@app.post('/demo/seed')
def seed(actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    if db.scalar(select(LegalEntity).where(LegalEntity.org_id==actor.org_id,LegalEntity.code=='DEMO-US')): return {'imported':0,'notice':'Demo workspace already exists'}
    primary=LegalEntity(id=uid(),org_id=actor.org_id,code='DEMO-US',name='Atlas Services US',currency='USD');db.add(primary);db.flush()
    europe=LegalEntity(id=uid(),org_id=actor.org_id,code='DEMO-EU',name='Atlas Services Europe',currency='EUR',parent_id=primary.id);db.add(europe);db.flush()
    chart=[('1000','Cash','asset',True),('1100','Receivables','asset',False),('2000','Payables','liability',False),('3000','Capital','equity',False),('4000','Service revenue','revenue',False),('5000','Operating expenses','expense',False)]
    for entity in (primary,europe):
        for code,name,category,cash in chart: db.add(Account(id=uid(),org_id=actor.org_id,entity_id=entity.id,code=code,name=name,category=category,is_cash=cash,group_code=code))
    db.flush()
    def entry(ref,description,lines): return JournalInput.model_validate({'external_id':ref,'posting_date':'2026-10-01','currency':'USD','description':description,'lines':[{'account_code':code,'debit':debit,'credit':credit,'reference':reference} for code,debit,credit,reference in lines]})
    samples=[entry('OPEN-001','Opening capital',[('1000','100000','0','OPEN'),('3000','0','100000','OPEN')]),entry('INV-001','Service invoice',[('1100','15000','0','INV-001'),('4000','0','15000','INV-001')]),entry('REC-001','Customer receipt',[('1000','15000','0','REC-001'),('1100','0','15000','REC-001')]),entry('BILL-001','Vendor bill',[('5000','1200','0','BILL-001'),('2000','0','1200','BILL-001')]),entry('PAY-001','Vendor payment',[('2000','1200','0','PAY-001'),('1000','0','1200','PAY-001')]),entry('INV-DUP','Possible duplicate invoice',[('1100','15000','0','INV-001'),('4000','0','15000','INV-001')])]
    result=finance.ingest_journals(db,actor,primary.id,'manual',samples)
    finance.ingest_journals(db,actor,europe.id,'manual',[JournalInput.model_validate({'external_id':'EU-OPEN','posting_date':'2026-10-01','currency':'EUR','description':'Opening capital','lines':[{'account_code':'1000','debit':'20000','credit':'0'},{'account_code':'3000','debit':'0','credit':'20000'}]})])
    for ref,value in [('REC-001','15000'),('PAY-001','-1195')]: db.add(BankTransaction(id=uid(),org_id=actor.org_id,entity_id=primary.id,external_id='BANK-'+ref,date='2026-10-02',amount=Decimal(value),reference=ref,currency='USD'))
    for ref,when,value,direction in [('AR-001','2026-10-09','25000','inflow'),('AP-001','2026-10-12','8000','outflow'),('PAYROLL','2026-10-16','18000','outflow')]: db.add(PaymentSchedule(id=uid(),org_id=actor.org_id,entity_id=primary.id,reference=ref,due_date=when,amount=Decimal(value),direction=direction))
    first=PlatformTask(id=uid(),org_id=actor.org_id,entity_id=primary.id,title='Review duplicate invoice and source evidence',owner_id=actor.user_id,due_date='2026-10-05',period='2026-10',depends_on=[]);db.add(first);db.flush()
    db.add(PlatformTask(id=uid(),org_id=actor.org_id,entity_id=primary.id,title='Controller sign-off',owner_id=actor.user_id,due_date='2026-10-07',period='2026-10',depends_on=[first.id]))
    finance.audit(db,actor,'demo_workspace_created',primary.id);db.commit();return {**result,'entity_id':primary.id,'secondary_entity_id':europe.id}

@app.post('/legacy/import')
async def legacy_import(entity_id:str=Form(...),mapping:str=Form('{}'),file:UploadFile=File(...),actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    preview=await legacy_preview(entity_id,mapping,file,actor,db)
    if not preview['valid']: raise HTTPException(422,preview['errors'])
    await file.seek(0);raw=await file.read(2_000_001)
    result=finance.ingest_journals(db,actor,entity_id,'legacy-csv',[JournalInput.model_validate(p) for p in preview['journals']])
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='csv_import',inputs={'entity_id':entity_id,'mapping':preview['selected_mapping'],'source_sha256':preview['source_sha256'],'source_csv':raw.decode('utf-8-sig'),'transform_version':preview['transform_version']},output=result);db.add(run)
    finance.audit(db,actor,'legacy_csv_imported',run.id,{'sha256':preview['source_sha256'],'journal_ids':result['journal_ids']});db.commit();return {'run_id':run.id,**result}

@app.post('/budgets',status_code=201)
def add_budget(body:BudgetInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,body.entity_id,actor);finance.period_dates(body.period)
    account=db.scalar(select(Account).where(Account.org_id==actor.org_id,Account.entity_id==body.entity_id,Account.code==body.account_code))
    if not account or account.category not in ('revenue','expense'): raise HTTPException(422,'Budgets require a mapped revenue or expense account')
    latest=db.scalar(select(BudgetLine).where(BudgetLine.org_id==actor.org_id,BudgetLine.entity_id==body.entity_id,BudgetLine.period==body.period,BudgetLine.account_id==account.id).order_by(BudgetLine.version.desc()).limit(1))
    if body.version!=(latest.version+1 if latest else 1): raise HTTPException(422,'Budget versions must be sequential')
    row=BudgetLine(id=uid(),org_id=actor.org_id,entity_id=body.entity_id,period=body.period,account_id=account.id,amount=body.amount,version=body.version,created_by=actor.user_id);db.add(row)
    finance.audit(db,actor,'budget_version_created',row.id,body.model_dump(mode='json'));db.commit();return {'id':row.id}

@app.get('/reports/budget')
def budget_report(entity_id:str,period:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    scoped(db,LegalEntity,entity_id,actor);start,end=finance.period_dates(period)
    budgets=db.scalars(select(BudgetLine).where(BudgetLine.org_id==actor.org_id,BudgetLine.entity_id==entity_id,BudgetLine.period==period).order_by(BudgetLine.version)).all()
    latest={b.account_id:b for b in budgets};rows=[]
    for account in finance.trial_balance(db,actor.org_id,entity_id,start,end):
        if account['category'] not in ('revenue','expense'): continue
        budget=latest.get(account['account_id']);actual=Decimal(account['balance'])*(-1 if account['category']=='revenue' else 1)
        rows.append({'code':account['code'],'name':account['name'],'category':account['category'],'actual':finance.amount(actual),'budget':finance.amount(budget.amount) if budget else None,'variance':finance.amount(actual-budget.amount) if budget else None,'budget_version':budget.version if budget else None})
    return {'period':period,'rows':rows,'variance_basis':'Actual minus budget; a positive expense variance represents spending above budget'}

@app.get('/reports/budget-review-changes')
def budget_review_changes(earlier_id:str,later_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    earlier=scoped(db,AnalysisRun,earlier_id,actor);later=scoped(db,AnalysisRun,later_id,actor)
    if earlier.id==later.id: raise HTTPException(422,'Choose two different snapshots')
    if any(r.kind!='budget_exceptions' for r in (earlier,later)): raise HTTPException(422,'Choose saved budget exception reviews')
    if any(earlier.output[k]!=later.output[k] for k in ('entity_id','period','currency')): raise HTTPException(422,'Reviews must use the same entity, period and currency')
    if earlier.created_at>later.created_at: raise HTTPException(422,'Earlier review must precede later review')
    old={r['code']:r for r in earlier.output['rows']};new={r['code']:r for r in later.output['rows']};rows=[]
    for code in sorted(set(old)|set(new)):
        before=old.get(code);after=new.get(code)
        changed=before!=after
        delta=Decimal(after['actual'])-Decimal(before['actual']) if before and after else None
        rows.append({'code':code,'name':(after or before)['name'],'change':'added' if before is None else 'removed' if after is None else 'changed' if changed else 'unchanged','actual_before':before['actual'] if before else None,'actual_after':after['actual'] if after else None,'actual_change':finance.amount(delta) if delta is not None else None,'budget_before':before['budget'] if before else None,'budget_after':after['budget'] if after else None,'version_before':before['budget_version'] if before else None,'version_after':after['budget_version'] if after else None,'review_before':before['review_required'] if before else None,'review_after':after['review_required'] if after else None})
    return {'earlier_id':earlier.id,'later_id':later.id,'earlier_saved_at':earlier.created_at.isoformat(),'later_saved_at':later.created_at.isoformat(),'entity_id':later.output['entity_id'],'period':later.output['period'],'currency':later.output['currency'],'materiality_before':earlier.output['materiality'],'materiality_after':later.output['materiality'],'changed_accounts':sum(r['change']!='unchanged' for r in rows),'rows':rows,'basis':'Comparison of frozen review snapshots, not current ledger values. Review flags can change when materiality changes; this is not evidence that an accounting issue was resolved.'}

@app.post('/reports/budget-exceptions',status_code=201)
def budget_exceptions(body:BudgetExceptionInput,actor:Principal=Depends(writer),db:Session=Depends(db_session)):
    entity=scoped(db,LegalEntity,body.entity_id,actor)
    report=budget_report(body.entity_id,body.period,actor,db)
    rows=[];impact=Decimal('0')
    for row in report['rows']:
        variance=Decimal(row['variance']) if row['variance'] is not None else None
        earnings=variance*(1 if row['category']=='revenue' else -1) if variance is not None else None
        if earnings is not None: impact+=earnings
        adverse=max(Decimal('0'),-earnings) if earnings is not None else None
        budget=Decimal(row['budget']) if row['budget'] is not None else None
        flag=(adverse is not None and adverse>0 and adverse>=body.materiality) or (budget is None and abs(Decimal(row['actual']))>0 and abs(Decimal(row['actual']))>=body.materiality)
        rows.append({**row,'earnings_impact':finance.amount(earnings) if earnings is not None else None,'variance_percent':finance.amount(variance/budget*100) if budget else None,'review_required':flag,'reason':'missing_budget' if budget is None else 'adverse_material_variance' if flag else 'within_review_policy'})
    rows.sort(key=lambda r:(not r['review_required'],-abs(Decimal(r['earnings_impact'] or r['actual'])),r['code']))
    output={'entity_id':entity.id,'period':body.period,'currency':entity.currency,'materiality':finance.amount(body.materiality),'rows':rows,'exceptions':sum(r['review_required'] for r in rows),'unbudgeted_accounts':sum(r['budget'] is None for r in rows),'budgeted_earnings_impact':finance.amount(impact),'basis':'Actuals from active journals and latest account budget versions for this period. Earnings impact is revenue variance minus expense variance, limited to budgeted accounts. Missing budgets are disclosed; zero budgets have no percentage variance. Materiality is an absolute currency threshold, not an industry benchmark or accounting sign-off.'}
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='budget_exceptions',inputs=body.model_dump(mode='json'),output=output)
    db.add(run);finance.audit(db,actor,'budget_exceptions_created',run.id);db.commit()
    return {'id':run.id,**output}

@app.post('/intercompany/runs')
def intercompany_run(body:ConsolidationInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    output=finance.intercompany_matches(db,actor,body)
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='intercompany_matching',inputs=body.model_dump(mode='json'),output=output);db.add(run)
    finance.audit(db,actor,'intercompany_matching_created',run.id,{'matches':len(output['matches'])});db.commit();return {'id':run.id,**output}

@app.post('/consolidation/elimination-proposals',status_code=201)
def elimination_proposal(body:EliminationInput,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    run=scoped(db,AnalysisRun,body.source_run_id,actor)
    if run.kind!='intercompany_matching' or not run.output.get('proposed_elimination_rows'): raise HTTPException(422,'Use a matching run with balanced reciprocal claims')
    if sum((Decimal(r['balance']) for r in run.output['proposed_elimination_rows']),Decimal('0')): raise HTTPException(422,'Elimination draft must balance')
    proposal=GroupElimination(id=uid(),org_id=actor.org_id,source_run_id=run.id,submitted_by=actor.user_id,reason=body.reason);db.add(proposal)
    finance.audit(db,actor,'elimination_proposed',proposal.id,{'source_run_id':run.id});db.commit();return {'id':proposal.id}

@app.get('/consolidation/elimination-proposals')
def elimination_proposals(actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    return [{'id':p.id,'source_run_id':p.source_run_id,'submitted_by':p.submitted_by,'status':p.status,'reason':p.reason,'decision_note':p.decision_note,'rows':db.get(AnalysisRun,p.source_run_id).output['proposed_elimination_rows']} for p in db.scalars(select(GroupElimination).where(GroupElimination.org_id==actor.org_id)).all()]

@app.post('/consolidation/elimination-proposals/{proposal_id}/decision')
def elimination_decision(proposal_id:str,body:Decision,actor:Principal=Depends(controller),db:Session=Depends(db_session)):
    proposal=scoped(db,GroupElimination,proposal_id,actor)
    if proposal.submitted_by==actor.user_id: raise HTTPException(403,'Independent reviewer required')
    changed=db.execute(update(GroupElimination).where(GroupElimination.id==proposal.id,GroupElimination.org_id==actor.org_id,GroupElimination.status=='pending').values(status=body.decision,reviewed_by=actor.user_id,decision_note=body.note))
    if changed.rowcount!=1: raise HTTPException(409,'Elimination proposal already decided')
    finance.audit(db,actor,'elimination_decided',proposal.id,body.model_dump());db.commit();return {'status':body.decision}

@app.get('/reports/export')
def export_statements(entity_id:str,period:str,format:str='xlsx',actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    from .exports import workbook,pdf_report
    entity=scoped(db,LegalEntity,entity_id,actor);statement=finance.statements(db,actor.org_id,entity_id,period);start,end=finance.period_dates(period)
    if format=='xlsx': content=workbook(entity,statement,finance.trial_balance(db,actor.org_id,entity_id,start,end));media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif format=='pdf': content=pdf_report(entity,statement);media='application/pdf'
    else: raise HTTPException(422,'Supported formats: xlsx, pdf')
    run=AnalysisRun(id=uid(),org_id=actor.org_id,actor_id=actor.user_id,kind='report_snapshot',inputs={'entity_id':entity_id,'period':period,'format':format},output={'statement':statement,'sha256':hashlib.sha256(content).hexdigest()});db.add(run)
    finance.audit(db,actor,'report_exported',run.id,{'format':format,'sha256':run.output['sha256']});db.commit()
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="financial-report.{format}"','X-Content-Type-Options':'nosniff'})

@app.get('/analytics/charts')
def analytics_charts(entity_id:str,period:str='2026-10',actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    from .intelligence_suite import compute_analytics_charts
    return compute_analytics_charts(db,actor.org_id,entity_id,period)

@app.post('/copilot/simulate')
def copilot_simulation(body:dict,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    from .intelligence_suite import simulate_copilot_scenario
    entity_id=body.get('entity_id','')
    return simulate_copilot_scenario(db,actor.org_id,entity_id,body)

@app.get('/integrity/anomalies')
def integrity_anomalies(entity_id:str,actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    from .intelligence_suite import detect_anomalies
    return detect_anomalies(db,actor.org_id,entity_id)

@app.get('/executive/deck')
def executive_deck(entity_id:str,period:str='2026-10',actor:Principal=Depends(principal),db:Session=Depends(db_session)):
    from .intelligence_suite import generate_executive_deck
    return generate_executive_deck(db,actor.org_id,entity_id,period)











