"""Reference-based collection evidence; never changes accounting records."""
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from .auth import scoped
from .platform_models import LegalEntity, PaymentSchedule, BankTransaction
from .finance_engine import amount


def assess(db, actor, entity_id, as_of):
    if as_of > datetime.now(timezone.utc).date():
        raise HTTPException(422, 'Review date cannot be in the future')
    entity = scoped(db, LegalEntity, entity_id, actor)
    payments = db.scalars(select(PaymentSchedule).where(PaymentSchedule.org_id == actor.org_id, PaymentSchedule.entity_id == entity.id, PaymentSchedule.direction == 'inflow')).all()
    bank = db.scalars(select(BankTransaction).where(BankTransaction.org_id == actor.org_id, BankTransaction.entity_id == entity.id, BankTransaction.currency == entity.currency, BankTransaction.date <= as_of.isoformat()).order_by(BankTransaction.date, BankTransaction.id)).all()
    buckets = {key: Decimal('0') for key in ('not_due', '1_30', '31_60', '61_90', 'over_90')}
    rows = []
    used = set()
    for p in payments:
        # Exact references only; negative movements can represent a refund/reversal.
        matched = [b for b in bank if b.reference and b.reference == p.reference]
        used.update(b.id for b in matched)
        net = sum((b.amount for b in matched), Decimal('0'))
        credited = min(p.amount, max(Decimal('0'), net))
        outstanding = p.amount - credited
        overdue = max(0, (as_of - date.fromisoformat(p.due_date)).days)
        bucket = 'not_due' if overdue == 0 else ('1_30' if overdue <= 30 else '31_60' if overdue <= 60 else '61_90' if overdue <= 90 else 'over_90')
        buckets[bucket] += outstanding
        rows.append({'schedule_id': p.id, 'reference': p.reference, 'due_date': p.due_date, 'expected': amount(p.amount), 'net_bank_evidence': amount(net), 'outstanding': amount(outstanding), 'excess_receipts': amount(max(Decimal('0'), net-p.amount)), 'days_overdue': overdue, 'bucket': bucket, 'status': 'covered_by_bank_evidence' if outstanding == 0 else 'partial_evidence' if credited > 0 else 'no_positive_net_evidence', 'bank_ids': [b.id for b in matched]})
    rows.sort(key=lambda r: (-Decimal(r['outstanding']), -r['days_overdue'], r['reference']))
    total = sum((Decimal(r['outstanding']) for r in rows), Decimal('0'))
    top = sum((Decimal(r['outstanding']) for r in rows[:5]), Decimal('0'))
    return {'entity_id': entity.id, 'currency': entity.currency, 'as_of': as_of.isoformat(), 'outstanding': amount(total), 'overdue': amount(sum((v for k,v in buckets.items() if k != 'not_due'), Decimal('0'))), 'largest_five_share_percent': amount(top * 100 / total) if total else None, 'aging': [{'bucket': k, 'outstanding': amount(v)} for k,v in buckets.items()], 'rows': rows, 'unlinked_positive_bank_ids': [b.id for b in bank if b.amount > 0 and b.id not in used], 'basis': 'Exact, case-sensitive schedule/reference matches against imported bank movements through the review date. Negative same-reference movements reduce net receipt evidence. No fuzzy allocation, invoice settlement, customer identity or bank completeness is certified. Outstanding amounts are collection-review estimates, not the accounts-receivable ledger. Largest-five share measures schedule concentration, not customer concentration.'}
