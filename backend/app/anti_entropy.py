"""Exact bounded manifest comparison; no automatic money merge or deletion."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from .auth import scoped, uid
from .platform_models import ReconciliationPolicy, SourceRecord, AnalysisRun, IntegrationMessage, LegalEntity, ERPConnection, now
from . import finance_engine as finance
from .event_pipeline import lock, process

def utc(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def parse_stamp(value):
    try:
        stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
        if stamp.tzinfo is None: raise ValueError()
        return utc(stamp)
    except ValueError: raise HTTPException(422,'Observation requires a timezone-aware ISO timestamp')

def policy(db,actor):
    row=db.get(ReconciliationPolicy,actor.org_id)
    return {'max_pending_seconds':row.max_pending_seconds if row else 300,'max_source_age_seconds':row.max_source_age_seconds if row else 3600,'reconciliation_interval_seconds':row.reconciliation_interval_seconds if row else 30}

def update_policy(db,actor,body):
    lock(db,actor)
    row=db.get(ReconciliationPolicy,actor.org_id)
    if row is None: row=ReconciliationPolicy(org_id=actor.org_id);db.add(row)
    for key,value in body.model_dump().items(): setattr(row,key,value)
    finance.audit(db,actor,'reconciliation_policy_updated',actor.org_id,body.model_dump())
    return body.model_dump()

def latest_sources(db,actor,entity,connection):
    result={}
    for source in db.scalars(select(SourceRecord).where(SourceRecord.org_id==actor.org_id,SourceRecord.entity_id==entity,SourceRecord.connection_id==connection)).all():
        if source.external_id not in result or source.version>result[source.external_id].version: result[source.external_id]=source
    return result

def local_manifest(db,actor,entity,connection):
    scoped(db,LegalEntity,entity,actor)
    if connection not in ('manual','csv','legacy-csv'):
        row=scoped(db,ERPConnection,connection,actor)
        if row.entity_id!=entity: raise HTTPException(422,'Connection entity mismatch')
    sources=latest_sources(db,actor,entity,connection)
    if len(sources)>10000: raise HTTPException(422,'Manifest exceeds bounded limit; partition source before reconciliation')
    records=[{'external_id':s.external_id,'version':s.version,'payload_hash':s.payload_hash,'tombstone':bool(s.payload.get('tombstone'))} for s in sorted(sources.values(),key=lambda s:s.external_id)]
    return {'entity_id':entity,'connection_id':connection,'records':records,'manifest_hash':finance.hash_json(records),'generated_at':now().isoformat()}

def differences(db,actor,body):
    local=local_manifest(db,actor,body.entity_id,body.connection_id)
    remote={r.external_id:r.model_dump() for r in body.records}
    if len(remote)!=len(body.records): raise HTTPException(422,'Duplicate source identities in manifest')
    indexed={r['external_id']:r for r in local['records']}
    missing=[];unexpected=[];divergent=[];corrupt=[]
    for identity in sorted(remote):
        if identity not in indexed: missing.append(identity)
        elif indexed[identity]!=remote[identity]: divergent.append({'external_id':identity,'local':indexed[identity],'remote':remote[identity]})
    unexpected=sorted(set(indexed)-set(remote))
    for identity,source in latest_sources(db,actor,body.entity_id,body.connection_id).items():
        if finance.hash_json(source.payload)!=source.payload_hash: corrupt.append(identity)
    return {'missing_local':missing,'unexpected_local':unexpected,'divergent':divergent,'corrupt_local':corrupt,'converged':not(missing or unexpected or divergent or corrupt),'local_manifest_hash':local['manifest_hash'],'remote_manifest_hash':finance.hash_json(sorted(remote.values(),key=lambda r:r['external_id'])),'scope':'Exact submitted manifest; no independent source completeness certification'}

def compare(db,actor,body):
    lock(db,actor)
    stamp=parse_stamp(body.observed_at)
    if stamp>now(): raise HTTPException(422,'Observation cannot be in the future')
    prior=db.scalars(select(AnalysisRun).where(AnalysisRun.org_id==actor.org_id,AnalysisRun.kind=='source_manifest').order_by(AnalysisRun.created_at.desc())).all()
    for run in prior:
        if run.inputs['entity_id']==body.entity_id and run.inputs['connection_id']==body.connection_id:
            if stamp<=parse_stamp(run.inputs['observed_at']): raise HTTPException(409,'Manifest must advance the observation timestamp')
            break
    result=differences(db,actor,body)
    run=AnalysisRun(id=uid(),org_id=actor.org_id,kind='source_manifest',actor_id=actor.user_id,inputs=body.model_dump(mode='json'),output=result)
    db.add(run);finance.audit(db,actor,'source_manifest_compared',run.id,{'converged':result['converged'],'watermark':body.watermark})
    return {'id':run.id,**result}

def freshness(db,actor):
    config=policy(db,actor);stamp=now()
    pending=db.scalars(select(IntegrationMessage).where(IntegrationMessage.org_id==actor.org_id,IntegrationMessage.status!='applied')).all()
    age=max((max(0,(stamp-utc(r.received_at)).total_seconds()) for r in pending),default=0)
    observations=[];seen=set()
    runs=db.scalars(select(AnalysisRun).where(AnalysisRun.org_id==actor.org_id,AnalysisRun.kind=='source_manifest').order_by(AnalysisRun.created_at.desc())).all()
    for run in runs:
        key=(run.inputs['entity_id'],run.inputs['connection_id'])
        if key in seen: continue
        seen.add(key);source_age=max(0,(stamp-parse_stamp(run.inputs['observed_at'])).total_seconds())
        from .contracts import SourceManifest
        current=differences(db,actor,SourceManifest.model_validate(run.inputs))
        observations.append({'entity_id':key[0],'connection_id':key[1],'watermark':run.inputs['watermark'],'age_seconds':source_age,'stale':source_age>config['max_source_age_seconds'],'converged':current['converged'],'differences':current,'run_id':run.id})
    return {'policy':config,'oldest_pending_age_seconds':age,'pending_threshold_exceeded':bool(pending) and age>config['max_pending_seconds'],'sources':observations,'upstream_status':'unverified' if not observations else 'observed_manifests_only','threshold_semantics':'Detection thresholds, not a hard replication latency guarantee'}

def reconcile_due(db,actor):
    lock(db,actor)
    row=db.get(ReconciliationPolicy,actor.org_id)
    if row is None: row=ReconciliationPolicy(org_id=actor.org_id);db.add(row);db.flush()
    if row.last_checked_at and (now()-utc(row.last_checked_at)).total_seconds()<row.reconciliation_interval_seconds: return {'due':False}
    result=process(db,actor)
    state=freshness(db,actor)
    summary={'pending_threshold_exceeded':state['pending_threshold_exceeded'],'oldest_pending_age_seconds':state['oldest_pending_age_seconds'],'sources':[{'entity_id':s['entity_id'],'connection_id':s['connection_id'],'stale':s['stale'],'converged':s['converged']} for s in state['sources']]}
    # Persist actionable checks only; healthy idle ticks do not grow the audit log.
    if summary['pending_threshold_exceeded'] or any(s['stale'] or not s['converged'] for s in summary['sources']):
        db.add(AnalysisRun(id=uid(),org_id=actor.org_id,kind='reconciliation_check',actor_id=actor.user_id,inputs={'policy':state['policy']},output=summary))
        finance.audit(db,actor,'reconciliation_threshold_alert',actor.org_id,summary)
    row.last_checked_at=now()
    result['due']=True
    result['freshness']=summary
    return result
