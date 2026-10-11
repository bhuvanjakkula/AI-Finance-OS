"""Review frozen forecast movements against imported bank records."""
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from .auth import scoped
from .platform_models import AnalysisRun, BankTransaction, LegalEntity
from .finance_engine import amount


def review(db, actor, run_id, as_of, tolerance):
    if as_of > datetime.now(timezone.utc).date():
        raise HTTPException(422, 'Review date cannot be in the future')
    run = scoped(db, AnalysisRun, run_id, actor)
    if run.kind != 'cash_forecast':
        raise HTTPException(422, 'Select a cash forecast snapshot')
    entity = scoped(db, LegalEntity, run.inputs['entity_id'], actor)
    records = db.scalars(select(BankTransaction).where(
        BankTransaction.org_id == actor.org_id,
        BankTransaction.entity_id == entity.id,
        BankTransaction.currency == entity.currency,
    ).order_by(BankTransaction.date, BankTransaction.id)).all()
    rows = []
    for week in run.output['weeks']:
        if date.fromisoformat(week['end']) > as_of:
            continue
        bank = [b for b in records if week['start'] <= b.date <= week['end']]
        incoming = sum((b.amount for b in bank if b.amount > 0), Decimal('0'))
        outgoing = sum((-b.amount for b in bank if b.amount < 0), Decimal('0'))
        predicted = Decimal(week['inflow']) - Decimal(week['outflow'])
        actual = incoming - outgoing
        error = actual - predicted
        rows.append({
            'week': week['week'], 'start': week['start'], 'end': week['end'],
            'forecast_net': amount(predicted), 'imported_net': amount(actual),
            'inflow_error': amount(incoming - Decimal(week['inflow'])),
            'outflow_error': amount(outgoing - Decimal(week['outflow'])),
            'net_error': amount(error), 'bank_ids': [b.id for b in bank],
            'status': 'no_bank_records' if not bank else ('review' if abs(error) > tolerance else 'within_tolerance'),
        })
    observed = [r for r in rows if r['bank_ids']]
    mae = sum((abs(Decimal(r['net_error'])) for r in observed), Decimal('0')) / len(observed) if observed else None
    return {
        'forecast_id': run.id, 'entity_id': entity.id, 'currency': entity.currency,
        'as_of': as_of.isoformat(), 'tolerance': amount(tolerance), 'weeks': rows,
        'observed_weeks': len(observed), 'mean_absolute_net_error': amount(mae) if mae is not None else None,
        'retrospective': run.created_at.date() >= date.fromisoformat(run.inputs['start_date']),
        'basis': 'Completed weeks only. Actuals are imported bank movements; bank coverage is not certified. Missing records are not treated as proven zero cash flow. Errors are actual minus forecast. This comparison does not estimate closing bank balances or predictive confidence.',
    }
