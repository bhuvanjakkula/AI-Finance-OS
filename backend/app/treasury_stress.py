"""Deterministic stresses on frozen weekly cash flows; no market probabilities."""
from decimal import Decimal, ROUND_HALF_EVEN
from fastapi import HTTPException
from .auth import scoped
from .platform_models import AnalysisRun, LegalEntity
from .finance_engine import amount


def assess(db, actor, body):
    run = scoped(db, AnalysisRun, body.forecast_id, actor)
    if run.kind != 'cash_forecast':
        raise HTTPException(422, 'Select a cash forecast snapshot')
    entity = scoped(db, LegalEntity, run.inputs['entity_id'], actor)
    weeks = run.output['weeks']
    opening = Decimal(weeks[0]['opening'])
    profiles = [
        ('Baseline', 0, Decimal('1'), Decimal('1')),
        ('Collections delayed', body.collection_delay_weeks, Decimal('1'), Decimal('1')),
        ('Reduced collections', 0, body.inflow_factor, Decimal('1')),
        ('Payment shock', 0, Decimal('1'), body.outflow_factor),
        ('Combined stress', body.collection_delay_weeks, body.inflow_factor, body.outflow_factor),
    ]
    results = []
    for name, delay, inflow_factor, outflow_factor in profiles:
        cash = opening
        minimum = opening
        first = 'opening' if opening < body.reserve else None
        rows = []
        deferred = Decimal('0')
        for i, week in enumerate(weeks):
            incoming = (Decimal(weeks[i-delay]['inflow']) * inflow_factor).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN) if i >= delay else Decimal('0')
            outgoing = (Decimal(week['outflow']) * outflow_factor).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)
            cash += incoming - outgoing
            minimum = min(minimum, cash)
            if first is None and cash < body.reserve:
                first = week['end']
            rows.append({'week': week['week'], 'end': week['end'], 'inflow': amount(incoming), 'outflow': amount(outgoing), 'closing': amount(cash), 'below_reserve': cash < body.reserve})
        for i, week in enumerate(weeks):
            if i + delay >= len(weeks):
                deferred += (Decimal(week['inflow']) * inflow_factor).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)
        results.append({'name': name, 'delay_weeks': delay, 'inflow_factor': str(inflow_factor), 'outflow_factor': str(outflow_factor), 'minimum_cash': amount(minimum), 'ending_cash': amount(cash), 'first_reserve_breach': first, 'funding_to_reserve': amount(max(Decimal('0'), body.reserve-minimum)), 'deferred_beyond_horizon': amount(deferred), 'weeks': rows})
    return {'source_forecast_id': run.id, 'entity_id': entity.id, 'currency': entity.currency, 'reserve': amount(body.reserve), 'scenarios': results, 'basis': 'Deterministic shocks to frozen weekly scenario flows, with no probabilities or market feed. Factors and delays apply on top of the saved forecast assumptions. Minimum cash includes opening cash and weekly closes; intraweek shortfalls are not modeled. Delayed receipts beyond the 13-week horizon are shown separately. Funding assumes cash is available at the start and excludes financing costs.'}
