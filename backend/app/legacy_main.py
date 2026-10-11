import csv, io
from decimal import Decimal
from datetime import date as CalendarDate
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from .models import LedgerLine, ExceptionRecord, AuditEvent, CloseTask
from .services import ingest, trial_balance

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="AI Finance OS API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

def get_db():
    with SessionLocal() as db:
        yield db

def get_tenant(x_tenant_id: str = Header(default="demo")):
    if not x_tenant_id.isalnum() or len(x_tenant_id) > 100:
        raise HTTPException(400, "Invalid tenant ID")
    return x_tenant_id

class LineInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=160)
    date: str
    account: str = Field(min_length=1, max_length=120)
    currency: str = Field(min_length=3, max_length=3)
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: str = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        return CalendarDate.fromisoformat(value).isoformat()

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value):
        if not value.isascii() or not value.isalpha():
            raise ValueError("Currency must contain three ASCII letters")
        return value.upper()

    @field_validator("debit", "credit")
    @classmethod
    def valid_money(cls, value):
        if not value.is_finite() or value < 0 or value >= Decimal("1000000000000000000"):
            raise ValueError("Amount must be finite, nonnegative and below 10^18")
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Amounts must have at most two decimal places")
        return value


@app.get("/health")
def health(): return {"status": "ok", "environment": "demo"}

@app.get("/modules")
def modules():
    return [{"name": n, "status": "demo" if i in (0,1,2,5) else "planned"} for i,n in enumerate(["Financial Close", "ERP Integration", "Financial Reporting", "Audit Automation", "Cash Forecasting", "Data Accuracy", "Legacy Modernization", "Multi-Entity Consolidation"])]

@app.post("/ledger/lines")
def create_lines(lines: list[LineInput], tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    if len(lines) > 10000: raise HTTPException(413, "Batch too large")
    try: return {"imported": ingest(db, tenant, [x.model_dump() for x in lines], "api")}
    except ValueError as e: db.rollback(); raise HTTPException(422, str(e))

@app.post("/imports/csv")
async def import_csv(file: UploadFile = File(...), tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000: raise HTTPException(413, "CSV too large")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        required = {"external_id", "date", "account", "currency", "debit", "credit"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("CSV is missing required ledger columns")
        lines = []
        for row in reader:
            if len(lines) >= 10000:
                raise ValueError("CSV exceeds 10,000 rows")
            lines.append(LineInput.model_validate(row).model_dump())
        return {"imported": ingest(db, tenant, lines)}
    except (ValueError, UnicodeError) as e:
        db.rollback(); raise HTTPException(422, str(e))

@app.post("/demo/seed")
def seed(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    sample = [
        {"external_id":"demo-1","date":"2026-09-30","account":"Cash","currency":"USD","debit":15000,"credit":0,"description":"Customer payment"},
        {"external_id":"demo-2","date":"2026-09-30","account":"Revenue","currency":"USD","debit":0,"credit":15000,"description":"Service revenue"},
        {"external_id":"demo-3","date":"2026-09-30","account":"Expenses","currency":"USD","debit":1200,"credit":0,"description":"Vendor invoice"},
        {"external_id":"demo-4","date":"2026-09-30","account":"Cash","currency":"USD","debit":0,"credit":1200,"description":"Vendor payment"},
        {"external_id":"demo-5","date":"2026-09-30","account":"Suspense","currency":"USD","debit":200,"credit":200,"description":"Potential posting issue"},
        {"external_id":"demo-6","date":"2026-09-30","account":"Suspense","currency":"USD","debit":0,"credit":0,"description":"Zero amount posting"}
    ]
    return {"imported": ingest(db, tenant, sample, "demo")}

@app.get("/reports/trial-balance")
def report(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    return {"rows": trial_balance(db, tenant), "notice": "Demo trial balance; no verified ERP mapping or financial statement classification"}

@app.get("/dashboard")
def dashboard(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    return {"lines": db.scalar(select(func.count()).select_from(LedgerLine).where(LedgerLine.tenant_id == tenant)), "open_exceptions": db.scalar(select(func.count()).select_from(ExceptionRecord).where(ExceptionRecord.tenant_id == tenant, ExceptionRecord.status == "open")), "tenant": tenant}

@app.get("/exceptions")
def exceptions(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    items = db.scalars(select(ExceptionRecord).where(ExceptionRecord.tenant_id == tenant).order_by(ExceptionRecord.id.desc())).all()
    return [{"id": x.id, "line_id": x.line_id, "rule": x.rule, "detail": x.detail, "status": x.status} for x in items]

@app.get("/exceptions/{exception_id}/investigate")
def investigate(exception_id: int, tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    e = db.scalar(select(ExceptionRecord).where(ExceptionRecord.id == exception_id, ExceptionRecord.tenant_id == tenant))
    if not e: raise HTTPException(404, "Exception not found")
    line = db.scalar(select(LedgerLine).where(LedgerLine.id == e.line_id, LedgerLine.tenant_id == tenant))
    return {"exception_id": e.id, "method": "deterministic_rules_not_ai", "explanation": f"Rule {e.rule} triggered on source record {line.external_id}: {e.detail}. Review the originating entry before any correction.", "evidence": {"external_id": line.external_id, "account": line.account, "source": line.source}, "recommendation": "Request controller review; no automatic posting"}

@app.post("/exceptions/{exception_id}/resolve")
def resolve(exception_id: int, tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    e = db.scalar(select(ExceptionRecord).where(ExceptionRecord.id == exception_id, ExceptionRecord.tenant_id == tenant))
    if not e: raise HTTPException(404, "Exception not found")
    e.status = "reviewed"
    db.add(AuditEvent(tenant_id=tenant, action="exception_reviewed", detail=f"Exception {exception_id} marked reviewed (demo only)"))
    db.commit()
    return {"status": e.status, "notice": "Demo workflow: no identity verification or approval authorization"}

@app.get("/audit/events")
def audit_events(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == tenant).order_by(AuditEvent.id.desc()).limit(100)).all()
    return [{"id":x.id,"action":x.action,"detail":x.detail,"created_at":x.created_at.isoformat()} for x in rows]


@app.get("/ledger/lines")
def ledger(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    rows = db.scalars(select(LedgerLine).where(LedgerLine.tenant_id == tenant).order_by(LedgerLine.id.desc()).limit(1000)).all()
    return [{"id": x.id, "external_id": x.external_id, "date": x.date, "account": x.account, "currency": x.currency, "debit": str(x.debit), "credit": str(x.credit), "description": x.description, "source": x.source} for x in rows]

@app.get("/reports/trial-balance.csv")
def export_report(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    from fastapi.responses import Response
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["account", "currency", "debit", "credit", "balance"])
    writer.writeheader()
    for row in trial_balance(db, tenant):
        # Prevent spreadsheet formula execution from imported account labels.
        if row["account"].startswith(("=", "+", "-", "@", "\t", "\r")):
            row["account"] = "'" + row["account"]
        writer.writerow(row)
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="trial-balance.csv"'})

class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    owner: str = Field(default="Controller", min_length=1, max_length=100)
    due_date: CalendarDate

class TaskUpdate(BaseModel):
    status: str
    @field_validator("status")
    @classmethod
    def valid_status(cls, value):
        if value not in ("todo", "in_progress", "complete"):
            raise ValueError("Invalid task status")
        return value

@app.get("/close/tasks")
def tasks(tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    rows = db.scalars(select(CloseTask).where(CloseTask.tenant_id == tenant).order_by(CloseTask.due_date)).all()
    return [{"id": t.id, "title": t.title, "owner": t.owner, "due_date": t.due_date, "status": t.status} for t in rows]

@app.post("/close/tasks", status_code=201)
def add_task(body: TaskInput, tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    task = CloseTask(tenant_id=tenant, title=body.title, owner=body.owner, due_date=body.due_date.isoformat())
    db.add(task)
    db.add(AuditEvent(tenant_id=tenant, action="close_task_created", detail=body.title))
    db.commit()
    return {"id": task.id}

@app.patch("/close/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate, tenant: str = Depends(get_tenant), db: Session = Depends(get_db)):
    task = db.scalar(select(CloseTask).where(CloseTask.id == task_id, CloseTask.tenant_id == tenant))
    if not task: raise HTTPException(404, "Task not found")
    task.status = body.status
    db.add(AuditEvent(tenant_id=tenant, action="close_task_updated", detail=f"Task {task_id}: {body.status}"))
    db.commit()
    return {"status": task.status}
