"""Find a conservative uniform collection loss limit on a frozen cash scenario."""
from decimal import Decimal, ROUND_FLOOR
from fastapi import HTTPException
from .auth import scoped
from .platform_models import AnalysisRun, LegalEntity
from .finance_engine import amount


def assess(db, actor, body):
    run = scoped(db, AnalysisRun, body.forecast_id, actor)
    if run.kind != 'cash_forecast':
        raise HTTPException(422, 'Select a cash forecast snapshot')
    entity = scoped(db, LegalEntity, run.inputs['entity_id'], actor)
    opening = Decimal(run.output['weeks'][0]['opening'])

    def path(loss_bps):
        factor = Decimal(10000-loss_bps)/10000
        cash = minimum = opening
        breach = 'opening' if cash < body.reserve else None
        rows = []
        for week in run.output['weeks']:
            incoming = (Decimal(week['inflow'])*factor).quantize(Decimal('.01'), rounding=ROUND_FLOOR)
            cash += incoming-Decimal(week['outflow'])
            minimum = min(minimum,cash)
            if breach is None and cash < body.reserve:
                breach = week['end']
            rows.append({'week':week['week'],'end':week['end'],'inflow':amount(incoming),'outflow':week['outflow'],'closing':amount(cash),'headroom':amount(cash-body.reserve)})
        return minimum,breach,rows

    base_min,base_breach,_ = path(0)
    zero_min,_,_ = path(10000)
    loss = None
    if base_breach is None:
        low,high = 0,10000
        while low < high:
            mid = (low+high+1)//2
            if path(mid)[1] is None: low = mid
            else: high = mid-1
        loss = low
    minimum,breach,rows = path(loss or 0)
    next_breach = path(loss+1)[1] if loss is not None and loss < 10000 else None
    return {'source_forecast_id':run.id,'entity_id':entity.id,'currency':entity.currency,'reserve':amount(body.reserve),'status':'baseline_breaches_reserve' if loss is None else 'all_collections_can_be_lost' if loss==10000 else 'limit_found','maximum_collection_loss_percent':amount(Decimal(loss)/100) if loss is not None else None,'first_breach_at_next_step':next_breach,'baseline_first_breach':base_breach,'baseline_funding_to_reserve':amount(max(Decimal('0'),body.reserve-base_min)),'funding_with_no_collections':amount(max(Decimal('0'),body.reserve-zero_min)),'minimum_cash_at_limit':amount(minimum),'weeks':rows,'basis':'Deterministic uniform reduction of every weekly inflow in the saved scenario. Outflows and timing remain fixed. Limit searched at 0.01 percentage-point resolution; retained weekly receipts round down to cents. Includes opening cash and weekly closes, not intraweek liquidity. No probability, credit-risk estimate or bank completeness assurance. Funding assumes additional cash available at the start with no financing costs.'}
