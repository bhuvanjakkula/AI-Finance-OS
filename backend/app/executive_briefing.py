"""Evidence-based executive review; no generated recommendations or mixed-currency totals."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from .platform_models import LegalEntity, AnalysisRun
from . import close_readiness, collections, finance_engine


def build(db, actor, period):
    finance_engine.period_dates(period)
    today = datetime.now(timezone.utc).date()
    entities = db.scalars(select(LegalEntity).where(LegalEntity.org_id == actor.org_id).order_by(LegalEntity.code)).all()
    runs = db.scalars(select(AnalysisRun).where(AnalysisRun.org_id == actor.org_id, AnalysisRun.kind.in_(['treasury_stress','liquidity_limits'])).order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).limit(500)).all()
    rows=[]
    for entity in entities:
        close=close_readiness.assess(db,actor,entity.id,period)
        receipts=collections.assess(db,actor,entity.id,today)
        stress=next((r for r in runs if r.output.get('entity_id')==entity.id and r.kind=='treasury_stress'),None)
        limits=next((r for r in runs if r.output.get('entity_id')==entity.id and r.kind=='liquidity_limits'),None)
        worst=max(stress.output['scenarios'],key=lambda s:Decimal(s['funding_to_reserve'])) if stress else None
        rows.append({'entity_id':entity.id,'entity':entity.name,'currency':entity.currency,'close_ready':close['ready_for_review'],'close_blockers':close['blockers'],'close_checks':close['checks'],'overdue_collections':receipts['overdue'],'outstanding_collections':receipts['outstanding'],'unlinked_receipts':len(receipts['unlinked_positive_bank_ids']),'stress_run_id':stress.id if stress else None,'stress_saved_at':stress.created_at.isoformat() if stress else None,'stress_source_forecast_id':stress.output['source_forecast_id'] if stress else None,'stress_reserve':stress.output['reserve'] if stress else None,'largest_stress_funding_gap':worst['funding_to_reserve'] if worst else None,'collection_loss_limit_percent':limits.output['maximum_collection_loss_percent'] if limits else None,'limit_status':limits.output['status'] if limits else 'not_tested','limit_run_id':limits.id if limits else None,'limit_saved_at':limits.created_at.isoformat() if limits else None,'attention':not close['ready_for_review'] or Decimal(receipts['overdue'])>0 or bool(worst and Decimal(worst['funding_to_reserve'])>0) or bool(limits and limits.output['status']=='baseline_breaches_reserve')})
    return {'period':period,'collection_as_of':today.isoformat(),'entities':rows,'entities_needing_review':sum(r['attention'] for r in rows),'basis':'Close and collection checks are current reads. Stress and loss limits are historical saved scenarios, potentially using different forecasts and reserves; inspect their source before comparison. Latest scenarios are selected from the most recent 500 stress/limit runs. No cross-currency totals, market feed, valuation or investment recommendation is produced.'}
