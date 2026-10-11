"""Durable inbox, ordered projection and transactional outbox. Single SQLite worker."""
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select, func
from .auth import scoped, uid
from .contracts import IntegrationInput, JournalInput
from .platform_models import Organization, LegalEntity, ERPConnection, IntegrationMessage, IntegrationOutbox, SourceRecord, now
from . import finance_engine as finance

def lock(db,actor):
    db.scalar(select(Organization).where(Organization.id==actor.org_id).with_for_update())

def receive(db,actor,body):
    lock(db,actor)
    scoped(db,LegalEntity,body.entity_id,actor)
    if body.connection_id not in ('manual','csv','legacy-csv'):
        connection=scoped(db,ERPConnection,body.connection_id,actor)
        if connection.entity_id!=body.entity_id: raise HTTPException(422,'Connection entity mismatch')
    try:
        stamp=datetime.fromisoformat(body.occurred_at.replace('Z','+00:00'))
        if stamp.tzinfo is None: raise ValueError()
    except ValueError: raise HTTPException(422,'occurred_at requires an ISO timestamp with timezone')
    if body.operation=='delete' and body.journal is not None: raise HTTPException(422,'Deletion must not contain journal lines')
    if body.operation!='delete':
        if not body.journal or body.journal.external_id!=body.external_id or body.journal.version!=body.version:
            raise HTTPException(422,'Journal identity/version must match event')
    envelope=body.model_dump(mode='json')
    if body.journal: envelope['journal']=finance.normalized_payload(body.journal)
    checksum=finance.hash_json(envelope)
    previous=db.scalar(select(IntegrationMessage).where(IntegrationMessage.org_id==actor.org_id,IntegrationMessage.connection_id==body.connection_id,IntegrationMessage.event_id==body.event_id))
    if previous:
        if previous.payload_hash!=checksum: raise HTTPException(409,'Event ID reused with different content')
        return {'id':previous.id,'status':previous.status,'replayed':True}
    row=IntegrationMessage(id=uid(),org_id=actor.org_id,entity_id=body.entity_id,connection_id=body.connection_id,event_id=body.event_id,external_id=body.external_id,version=body.version,envelope=envelope,payload_hash=checksum)
    db.add(row);db.flush()
    finance.audit(db,actor,'integration_received',row.id,{'hash':checksum,'operation':body.operation})
    return {'id':row.id,'status':'queued','replayed':False}

def process(db,actor):
    lock(db,actor)
    outcomes=[]
    ready_version=(select(func.coalesce(func.max(SourceRecord.version),0)+1).where(SourceRecord.org_id==IntegrationMessage.org_id,SourceRecord.entity_id==IntegrationMessage.entity_id,SourceRecord.connection_id==IntegrationMessage.connection_id,SourceRecord.external_id==IntegrationMessage.external_id).correlate(IntegrationMessage).scalar_subquery())
    pending=(IntegrationMessage.org_id==actor.org_id,IntegrationMessage.status.in_(['queued','waiting','failed']))
    gaps=db.scalars(select(IntegrationMessage).where(*pending,IntegrationMessage.status=='queued',IntegrationMessage.version>ready_version).order_by(IntegrationMessage.received_at).limit(100)).all()
    for gap in gaps:
        gap.status='waiting';gap.error='Missing predecessor version'
        outcomes.append({'id':gap.id,'status':'waiting'})
    db.flush()
    attempted=[]
    for _ in range(100):
        # Re-evaluate readiness after each commit-to-savepoint: a predecessor can
        # unlock the next version without letting blocked streams starve others.
        row=db.scalar(select(IntegrationMessage).where(*pending,IntegrationMessage.version<=ready_version,IntegrationMessage.id.not_in(attempted)).order_by(IntegrationMessage.version,IntegrationMessage.received_at).limit(1))
        if row is None: break
        attempted.append(row.id)
        try:
            with db.begin_nested():
                if finance.hash_json(row.envelope)!=row.payload_hash: raise HTTPException(409,'Stored envelope hash mismatch')
                body=IntegrationInput.model_validate(row.envelope)
                latest=db.scalar(select(SourceRecord).where(SourceRecord.org_id==actor.org_id,SourceRecord.entity_id==row.entity_id,SourceRecord.connection_id==row.connection_id,SourceRecord.external_id==row.external_id).order_by(SourceRecord.version.desc()).limit(1))
                expected=latest.version+1 if latest else 1
                if row.version>expected:
                    row.status='waiting';row.error=f'Missing version {expected}'
                    outcomes.append({'id':row.id,'status':row.status});continue
                if body.operation=='delete':
                    previous=db.scalar(select(finance.Journal).where(finance.Journal.source_id==latest.id)) if latest else None
                    if previous: finance.require_open_period(db,actor,row.entity_id,previous.period)
                    payload={'tombstone':True,'external_id':body.external_id,'version':body.version,'reason':body.reason,'occurred_at':body.occurred_at}
                    existing=db.scalar(select(SourceRecord).where(SourceRecord.org_id==actor.org_id,SourceRecord.entity_id==row.entity_id,SourceRecord.connection_id==row.connection_id,SourceRecord.external_id==row.external_id,SourceRecord.version==row.version))
                    if existing:
                        if existing.payload_hash!=finance.hash_json(payload): raise HTTPException(409,'Conflicting source revision')
                    else:
                        db.add(SourceRecord(id=uid(),org_id=actor.org_id,entity_id=row.entity_id,connection_id=row.connection_id,external_id=row.external_id,version=row.version,payload=payload,payload_hash=finance.hash_json(payload)))
                else:
                    if body.operation=='restore' and row.version==expected and (not latest or not latest.payload.get('tombstone')):
                        raise HTTPException(409,'Restore requires a tombstoned predecessor')
                    finance.ingest_journals(db,actor,row.entity_id,row.connection_id,[JournalInput.model_validate(body.journal)],allow_restore=body.operation=='restore')
                row.status='applied';row.error='';row.processed_at=now()
                db.add(IntegrationOutbox(id=uid(),org_id=actor.org_id,message_id=row.id,payload={'event_id':row.event_id,'external_id':row.external_id,'version':row.version,'operation':body.operation,'source_hash':row.payload_hash}))
                finance.audit(db,actor,'integration_applied',row.id,{'operation':body.operation,'version':row.version})
        except HTTPException as exc:
            row.attempts+=1;row.error=str(exc.detail)[:500]
            row.status='conflict' if exc.status_code==409 else ('dead_letter' if row.attempts>=3 else 'failed')
            finance.audit(db,actor,'integration_exception',row.id,{'status':row.status,'reason':row.error})
        outcomes.append({'id':row.id,'status':row.status})
    db.flush()
    return {'processed':outcomes,'bounded_batch':100,'gap_scan_limit':100}

def monitor(db,actor):
    rows=db.scalars(select(IntegrationMessage).where(IntegrationMessage.org_id==actor.org_id).order_by(IntegrationMessage.received_at.desc()).limit(500)).all()
    pending=db.scalars(select(IntegrationMessage).where(IntegrationMessage.org_id==actor.org_id,IntegrationMessage.status!='applied')).all()
    return {'messages':[{'id':r.id,'event_id':r.event_id,'external_id':r.external_id,'version':r.version,'operation':r.envelope['operation'],'status':r.status,'attempts':r.attempts,'error':r.error,'received_at':r.received_at.isoformat(),'processed_at':r.processed_at.isoformat() if r.processed_at else None} for r in rows],
        'unresolved':len(pending),'oldest_unresolved_at':min((r.received_at for r in pending),default=None),'projection_caught_up':not pending,
        'basis':'Received event backlog only; upstream source completeness is not certified'}

