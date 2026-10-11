from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import LedgerLine, ExceptionRecord, AuditEvent

def ingest(db: Session, tenant: str, rows: list[dict], source="csv"):
    added = 0
    for data in rows:
        if db.scalar(select(LedgerLine.id).where(LedgerLine.tenant_id == tenant, LedgerLine.external_id == data["external_id"])):
            existing = db.scalar(select(LedgerLine).where(LedgerLine.tenant_id == tenant, LedgerLine.external_id == data["external_id"]))
            if any(str(getattr(existing, key)) != str(data[key]) for key in ("date", "account", "currency", "description")) or existing.debit != Decimal(str(data["debit"])) or existing.credit != Decimal(str(data["credit"])):
                raise ValueError("Conflicting duplicate external ID: " + data["external_id"])
            continue
        debit, credit = Decimal(str(data["debit"])), Decimal(str(data["credit"]))
        if debit < 0 or credit < 0:
            raise ValueError("Negative debit/credit values are not supported")
        line = LedgerLine(tenant_id=tenant, source=source, **data)
        db.add(line)
        db.flush()
        added += 1
        if debit > 0 and credit > 0:
            db.add(ExceptionRecord(tenant_id=tenant, line_id=line.id, rule="both_sides", detail="Both debit and credit are nonzero"))
        if debit == 0 and credit == 0:
            db.add(ExceptionRecord(tenant_id=tenant, line_id=line.id, rule="zero_amount", detail="Both debit and credit are zero"))
    db.add(AuditEvent(tenant_id=tenant, action="ingest", detail=f"{added} lines imported from {source}"))
    db.commit()
    return added

def trial_balance(db: Session, tenant: str):
    lines = db.scalars(select(LedgerLine).where(LedgerLine.tenant_id == tenant)).all()
    by_account = {}
    for line in lines:
        key = (line.account, line.currency)
        row = by_account.setdefault(key, {"account": line.account, "currency": line.currency, "debit": Decimal('0'), "credit": Decimal('0')})
        row["debit"] += Decimal(str(line.debit))
        row["credit"] += Decimal(str(line.credit))
    return [{**r, "debit": str(r["debit"]), "credit": str(r["credit"]), "balance": str(r["debit"]-r["credit"])} for r in by_account.values()]
