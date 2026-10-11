"""Deterministic accounting services; no model computes ledger totals."""
import calendar, hashlib, json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from sqlalchemy import select
from fastapi import HTTPException
from .auth import uid, scoped
from .contracts import JournalInput
from .platform_models import *

ZERO=Decimal('0.00')

def require_open_period(db,actor,entity_id,period):
    db.scalar(select(Organization).where(Organization.id==actor.org_id).with_for_update())
    state=db.scalar(select(PeriodControl).where(PeriodControl.org_id==actor.org_id,PeriodControl.entity_id==entity_id,PeriodControl.period>=period,PeriodControl.status.in_(['review','locked'])).limit(1))
    if state: raise HTTPException(409,'This change affects a frozen or locked period; reopen affected closes before changing records')
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def hash_json(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def amount(value): return format(Decimal(value).quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN),'f')

def audit(db,actor,action,resource,detail=None):
    # PostgreSQL serializes each organization's chain; one SQLite writer is recommended.
    db.scalar(select(Organization).where(Organization.id==actor.org_id).with_for_update())
    latest=db.scalar(select(PlatformEvent).where(PlatformEvent.org_id==actor.org_id).order_by(PlatformEvent.id.desc()).limit(1))
    previous=latest.event_hash if latest else '0'*64
    stamp=now()
    payload={'actor_id':actor.user_id,'action':action,'resource_id':resource,'detail':detail or {},'created_at':stamp.isoformat(),'previous_hash':previous}
    event=PlatformEvent(org_id=actor.org_id,**{k:v for k,v in payload.items() if k!='created_at'},created_at=stamp,event_hash=hash_json(payload))
    db.add(event);db.flush()
    return event

def event_dict(event):
    return {'id':event.id,'actor_id':event.actor_id,'action':event.action,'resource_id':event.resource_id,'detail':event.detail,'created_at':event.created_at.replace(tzinfo=timezone.utc).isoformat(),'previous_hash':event.previous_hash,'event_hash':event.event_hash}

def verify_chain(db,org):
    previous='0'*64
    events=db.scalars(select(PlatformEvent).where(PlatformEvent.org_id==org).order_by(PlatformEvent.id)).all()
    for e in events:
        payload=event_dict(e);payload.pop('id');expected=payload.pop('event_hash')
        if payload['previous_hash']!=previous or hash_json(payload)!=expected:
            return {'valid':False,'first_invalid_event':e.id,'events':len(events)}
        previous=expected
    return {'valid':True,'events':len(events),'head_hash':previous}

def validate_journal(db,actor,entity,journal):
    if journal.currency!=entity.currency: raise HTTPException(422,'Journal currency must match entity functional currency; convert before import')
    codes={x.code:x for x in db.scalars(select(Account).where(Account.org_id==actor.org_id,Account.entity_id==entity.id)).all()}
    debit=credit=ZERO
    for line in journal.lines:
        if line.account_code not in codes: raise HTTPException(422,'Unmapped account: '+line.account_code)
        if (line.debit>0)==(line.credit>0): raise HTTPException(422,'Each journal line must have exactly one positive side')
        debit+=line.debit;credit+=line.credit
    if debit!=credit: raise HTTPException(422,f'Unbalanced journal {journal.external_id}: debit {debit}, credit {credit}')
    return codes

def normalized_payload(entry):
    payload=entry.model_dump(mode='json')
    payload['transaction_date']=payload['transaction_date'] or payload['posting_date']
    for line in payload['lines']:
        line['debit']=amount(line['debit']);line['credit']=amount(line['credit'])
    return payload

def ingest_journals(db,actor,entity_id,connection_id,journals,allow_restore=False):
    entity=scoped(db,LegalEntity,entity_id,actor)
    added=skipped=0; ids=[]
    fingerprint=lambda p: hash_json({'posting_date':p['posting_date'],'currency':p['currency'],'lines':p['lines']})
    all_sources=db.scalars(select(SourceRecord).where(SourceRecord.org_id==actor.org_id,SourceRecord.entity_id==entity_id)).all()
    latest_sources={}
    for source in all_sources:
        key=(source.connection_id,source.external_id)
        if key not in latest_sources or source.version>latest_sources[key].version: latest_sources[key]=source
    fingerprints={}
    for source in latest_sources.values():
        if not source.payload.get('tombstone'): fingerprints.setdefault(fingerprint(source.payload),set()).add((source.connection_id,source.external_id))
    for entry in journals:
        require_open_period(db,actor,entity_id,entry.posting_date.strftime('%Y-%m'))
        codes=validate_journal(db,actor,entity,entry)
        payload=normalized_payload(entry);checksum=hash_json(payload)
        key=(SourceRecord.org_id==actor.org_id,SourceRecord.entity_id==entity_id,SourceRecord.connection_id==connection_id,SourceRecord.external_id==entry.external_id)
        existing=db.scalar(select(SourceRecord).where(*key,SourceRecord.version==entry.version))
        if existing:
            if existing.payload_hash!=checksum: raise HTTPException(409,'Conflicting source version; import a new sequential version')
            skipped+=1;continue
        latest=db.scalar(select(SourceRecord).where(*key).order_by(SourceRecord.version.desc()).limit(1))
        if latest and latest.payload.get('tombstone') and not allow_restore: raise HTTPException(409,'Deleted source requires an explicit restore event')
        if entry.version!=(latest.version+1 if latest else 1): raise HTTPException(422,'Source versions must be sequential starting at 1')
        if latest and actor.role not in ('owner','controller'): raise HTTPException(403,'Controller role required to import revisions')
        previous=db.scalar(select(Journal).where(Journal.source_id==latest.id)) if latest else None
        if previous: require_open_period(db,actor,entity_id,previous.period)
        source=SourceRecord(id=uid(),org_id=actor.org_id,entity_id=entity_id,connection_id=connection_id,external_id=entry.external_id,version=entry.version,payload=payload,payload_hash=checksum)
        db.add(source);db.flush()
        journal=Journal(id=uid(),org_id=actor.org_id,entity_id=entity_id,source_id=source.id,external_id=entry.external_id,posting_date=entry.posting_date.isoformat(),transaction_date=(entry.transaction_date or entry.posting_date).isoformat(),period=entry.posting_date.strftime('%Y-%m'),currency=entry.currency,description=entry.description,supersedes_id=previous.id if previous else None)
        db.add(journal);db.flush()
        for line in entry.lines:
            db.add(JournalLine(id=uid(),org_id=actor.org_id,journal_id=journal.id,account_id=codes[line.account_code].id,debit=line.debit,credit=line.credit,reference=line.reference))
        if entry.posting_date>date.today():
            db.add(Finding(id=uid(),org_id=actor.org_id,journal_id=journal.id,rule='future_posting',severity='medium',detail='Posting date is in the future; confirm the intended accounting period'))
        # Identical lines/date under another source ID are a review hypothesis, never auto-deleted.
        identity=(connection_id,entry.external_id)
        signature=fingerprint(payload)
        if fingerprints.get(signature,set())-{identity}:
            db.add(Finding(id=uid(),org_id=actor.org_id,journal_id=journal.id,rule='possible_duplicate',severity='high',detail='Another source reference has identical date, currency and line amounts; inspect both documents'))
        if latest and not latest.payload.get('tombstone'): fingerprints.get(fingerprint(latest.payload),set()).discard(identity)
        fingerprints.setdefault(signature,set()).add(identity)
        added+=1;ids.append(journal.id)
    audit(db,actor,'journal_batch_imported',entity_id,{'connection_id':connection_id,'imported':added,'skipped':skipped,'journal_ids':ids})
    db.flush()
    return {'imported':added,'skipped':skipped,'journal_ids':ids}

def active_journals(db,org,entity_id=None,start=None,end=None):
    journals=db.scalars(select(Journal).where(Journal.org_id==org)).all()
    latest={}
    for source in db.scalars(select(SourceRecord).where(SourceRecord.org_id==org)).all():
        key=(source.entity_id,source.connection_id,source.external_id)
        if key not in latest or source.version>latest[key].version: latest[key]=source
    active={s.id for s in latest.values() if not s.payload.get('tombstone')}
    return [j for j in journals if j.source_id in active and (not entity_id or j.entity_id==entity_id) and (not start or j.posting_date>=start) and (not end or j.posting_date<=end)]

def journal_dict(db,journal):
    source=db.get(SourceRecord,journal.source_id)
    rows=db.scalars(select(JournalLine).where(JournalLine.journal_id==journal.id,JournalLine.org_id==journal.org_id)).all()
    accounts={a.id:a for a in db.scalars(select(Account).where(Account.org_id==journal.org_id)).all()}
    return {'id':journal.id,'entity_id':journal.entity_id,'external_id':journal.external_id,'posting_date':journal.posting_date,'transaction_date':journal.transaction_date or journal.posting_date,'period':journal.period or journal.posting_date[:7],'currency':journal.currency,'description':journal.description,'source_id':source.id,'source_hash':source.payload_hash,'version':source.version,'supersedes_id':journal.supersedes_id,'lines':[{'id':l.id,'account_code':accounts[l.account_id].code,'account_name':accounts[l.account_id].name,'category':accounts[l.account_id].category,'debit':amount(l.debit),'credit':amount(l.credit),'reference':l.reference} for l in rows]}

def trial_balance(db,org,entity_id,start=None,end=None):
    journals=active_journals(db,org,entity_id,start,end);ids={j.id for j in journals}
    accounts=db.scalars(select(Account).where(Account.org_id==org,Account.entity_id==entity_id)).all()
    totals={a.id:{'account_id':a.id,'code':a.code,'name':a.name,'category':a.category,'group_code':a.group_code,'is_cash':a.is_cash,'debit':ZERO,'credit':ZERO} for a in accounts}
    for line in db.scalars(select(JournalLine).where(JournalLine.org_id==org)).all():
        if line.journal_id in ids:
            totals[line.account_id]['debit']+=line.debit;totals[line.account_id]['credit']+=line.credit
    return [{**r,'debit':amount(r['debit']),'credit':amount(r['credit']),'balance':amount(r['debit']-r['credit'])} for r in totals.values()]

def period_dates(period):
    try:
        year,month=map(int,period.split('-'));start=date(year,month,1);end=date(year,month,calendar.monthrange(year,month)[1])
        return start.isoformat(),end.isoformat()
    except (ValueError,TypeError): raise HTTPException(422,'Period must be a valid YYYY-MM')

def statements(db,org,entity,period):
    start,end=period_dates(period)
    monthly=trial_balance(db,org,entity,start,end);cumulative=trial_balance(db,org,entity,end=end)
    pl=[];bs=[]
    for row in monthly:
        if row['category'] in ('revenue','expense'):
            value=Decimal(row['balance'])*(-1 if row['category']=='revenue' else 1)
            pl.append({**row,'amount':amount(value)})
    revenue=sum((Decimal(r['amount']) for r in pl if r['category']=='revenue'),ZERO)
    expenses=sum((Decimal(r['amount']) for r in pl if r['category']=='expense'),ZERO)
    cumulative_profit=ZERO
    for row in cumulative:
        value=Decimal(row['balance'])
        if row['category'] in ('revenue','expense'): cumulative_profit-=value;continue
        bs.append({**row,'amount':amount(value if row['category']=='asset' else -value)})
    assets=sum((Decimal(r['amount']) for r in bs if r['category']=='asset'),ZERO)
    liabilities=sum((Decimal(r['amount']) for r in bs if r['category']=='liability'),ZERO)
    equity=sum((Decimal(r['amount']) for r in bs if r['category']=='equity'),ZERO)
    return {'period':period,'profit_and_loss':pl,'balance_sheet':bs,'revenue':amount(revenue),'expenses':amount(expenses),'net_income':amount(revenue-expenses),'assets':amount(assets),'liabilities':amount(liabilities),'equity':amount(equity),'unclosed_earnings':amount(cumulative_profit),'balance_check':amount(assets-liabilities-equity-cumulative_profit),'journal_ids':[j.id for j in active_journals(db,org,entity,end=end)],'basis':'Imported active journal versions; source completeness and opening balances must be verified'}

def cash_forecast(db,actor,body):
    scoped(db,LegalEntity,body.entity_id,actor)
    payments=db.scalars(select(PaymentSchedule).where(PaymentSchedule.org_id==actor.org_id,PaymentSchedule.entity_id==body.entity_id)).all()
    cash=body.opening_cash;rows=[];included=[];overdue=[]
    for week in range(13):
        start=body.start_date+timedelta(days=week*7);end=start+timedelta(days=6);incoming=outgoing=ZERO
        for payment in payments:
            scheduled=date.fromisoformat(payment.due_date)
            if payment.direction=='inflow': scheduled+=timedelta(days=body.collection_delay_days)
            if start<=scheduled<=end:
                value=(payment.amount*(body.inflow_factor if payment.direction=='inflow' else body.outflow_factor)).quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)
                if payment.direction=='inflow': incoming+=value
                else: outgoing+=value
                included.append(payment.id)
        closing=cash+incoming-outgoing
        rows.append({'week':week+1,'start':start.isoformat(),'end':end.isoformat(),'opening':amount(cash),'inflow':amount(incoming),'outflow':amount(outgoing),'closing':amount(closing),'liquidity_warning':closing<0});cash=closing
    for p in payments:
        scheduled=date.fromisoformat(p.due_date)+(timedelta(days=body.collection_delay_days) if p.direction=='inflow' else timedelta())
        if scheduled<body.start_date: overdue.append(p.id)
    return {'weeks':rows,'payment_ids':included,'excluded_overdue_ids':overdue,'assumptions':body.model_dump(mode='json'),'method':'deterministic_payment_schedule_scenario','confidence':'Not estimated; payment realization probabilities are not modeled'}

def consolidate(db,actor,body):
    if len(set(body.entity_ids))!=len(body.entity_ids): raise HTTPException(422,'Duplicate entities in group')
    _,end=period_dates(body.period);totals={};sources=[]
    for entity_id in body.entity_ids:
        entity=scoped(db,LegalEntity,entity_id,actor)
        rate=Decimal('1') if entity.currency==body.group_currency else body.rates.get(entity_id)
        if rate is None or not rate.is_finite() or rate<=0 or rate>Decimal('1000000') or rate.as_tuple().exponent < -8:
            raise HTTPException(422,'Provide a positive FX rate with at most 8 decimal places for each foreign entity')
        for row in trial_balance(db,actor.org_id,entity_id,end=end):
            group=totals.setdefault(row['group_code'],{'group_code':row['group_code'],'category':row['category'],'balance':ZERO})
            if group['category']!=row['category']: raise HTTPException(422,'Group account classification conflicts between entities')
            group['balance']+=(Decimal(row['balance'])*rate).quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)
        sources.extend(j.id for j in active_journals(db,actor.org_id,entity_id,end=end))
    applied=[];used_lines=set()
    for identifier in body.approved_elimination_ids:
        if identifier in applied: raise HTTPException(422,'Duplicate elimination proposal')
        proposal=scoped(db,GroupElimination,identifier,actor)
        if proposal.status!='approved': raise HTTPException(409,'Elimination proposal must be independently approved')
        run=scoped(db,AnalysisRun,proposal.source_run_id,actor)
        if set(run.inputs['entity_ids'])!=set(body.entity_ids) or run.inputs['period']!=body.period or run.inputs['group_currency']!=body.group_currency:
            raise HTTPException(409,'Elimination group and reporting period do not match')
        if set(run.output['journal_ids'])!=set(sources): raise HTTPException(409,'Elimination source snapshot is stale; create a new matching run')
        for entity_id in body.entity_ids:
            entity=scoped(db,LegalEntity,entity_id,actor)
            if entity.currency!=body.group_currency and Decimal(run.inputs['rates'].get(entity_id,'0'))!=body.rates.get(entity_id):
                raise HTTPException(409,'Elimination FX snapshot does not match')
        line_ids={leg['line_id'] for match in run.output['matches'] for leg in (match['left'],match['right'])}
        if line_ids & used_lines: raise HTTPException(409,'Overlapping elimination proposals would double eliminate a claim')
        used_lines.update(line_ids)
        for row in run.output['proposed_elimination_rows']:
            target=totals.get(row['group_code'])
            if not target or target['category']!=row['category']: raise HTTPException(409,'Elimination group mapping no longer matches')
            target['balance']+=Decimal(row['balance'])
        applied.append(identifier)
    return {'period':body.period,'currency':body.group_currency,'rows':[{**r,'balance':amount(r['balance'])} for r in totals.values()],'journal_ids':sources,'applied_elimination_ids':applied,'translation_difference':amount(sum((r['balance'] for r in totals.values()),ZERO)),'scope':'Group trial-balance preview using supplied snapshot rates and selected approved reciprocal eliminations. No ownership accounting, CTA or historical equity rates. Not statutory consolidated statements.'}

def intercompany_matches(db,actor,body):
    import re
    group=consolidate(db,actor,body)
    entities={e.id:e for e in db.scalars(select(LegalEntity).where(LegalEntity.org_id==actor.org_id)).all()}
    by_code={e.code:e for e in entities.values()}
    _,end=period_dates(body.period)
    current=active_journals(db,actor.org_id,end=end)
    journals={j.id:j for j in current if j.entity_id in body.entity_ids}
    accounts={a.id:a for a in db.scalars(select(Account).where(Account.org_id==actor.org_id)).all()}
    claims=[]
    for line in db.scalars(select(JournalLine).where(JournalLine.org_id==actor.org_id)).all():
        if line.journal_id not in journals: continue
        tag=re.fullmatch(r'IC:([^:]+):(.+)',line.reference)
        if not tag: continue
        journal=journals[line.journal_id];entity=entities[journal.entity_id];counterparty=by_code.get(tag.group(1));account=accounts[line.account_id]
        if not counterparty or counterparty.id not in body.entity_ids or counterparty.id==entity.id:
            claims.append({'line_id':line.id,'status':'invalid_counterparty','reference':line.reference});continue
        rate=Decimal('1') if entity.currency==body.group_currency else body.rates[entity.id]
        value=(line.debit-line.credit)*rate
        claims.append({'line_id':line.id,'journal_id':journal.id,'entity_id':entity.id,'entity':entity.code,'counterparty_id':counterparty.id,'counterparty':counterparty.code,'reference':tag.group(2),'category':account.category,'group_code':account.group_code,'translated_amount':amount(value),'status':'unmatched'})
    matched=[];used=set();eliminations={}
    for claim in claims:
        if claim['status']!='unmatched' or claim['line_id'] in used: continue
        candidates=[c for c in claims if c.get('entity_id')==claim['counterparty_id'] and c.get('counterparty_id')==claim['entity_id'] and c.get('reference')==claim['reference'] and c['line_id'] not in used and Decimal(c.get('translated_amount','0'))==-Decimal(claim['translated_amount']) and {c.get('category'),claim['category']}=={'asset','liability'}]
        reverse_counts=[c for c in claims if c.get('entity_id')==claim['entity_id'] and c.get('counterparty_id')==claim['counterparty_id'] and c.get('reference')==claim['reference'] and c['line_id'] not in used and c.get('translated_amount')==claim['translated_amount']]
        if len(candidates)!=1 or len(reverse_counts)!=1:
            if candidates: claim['status']='ambiguous'
            continue
        counter=candidates[0];used.update([claim['line_id'],counter['line_id']]);claim['status']=counter['status']='matched'
        matched.append({'reference':claim['reference'],'left':claim,'right':counter})
        for leg in (claim,counter):
            code=leg['group_code'];item=eliminations.setdefault(code,{'group_code':code,'category':leg['category'],'balance':ZERO})
            item['balance']-=Decimal(leg['translated_amount'])
    return {'period':body.period,'currency':body.group_currency,'claims':claims,'matches':matched,'proposed_elimination_rows':[{**r,'balance':amount(r['balance'])} for r in eliminations.values()],'journal_ids':group['journal_ids'],'scope':'Exact reciprocal asset/liability claims tagged IC:COUNTERPARTY_CODE:REFERENCE, translated using supplied rates. Review before eliminating.'}
