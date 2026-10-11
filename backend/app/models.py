from datetime import datetime, timezone
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from decimal import Decimal
from sqlalchemy.types import TypeDecorator

class ExactMoney(TypeDecorator):
    """Decimal text avoids SQLite's implicit binary float conversion."""
    impl = String(24)
    cache_ok = True
    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Numeric(20,2) if dialect.name=='postgresql' else String(24))
    def process_bind_param(self, value, dialect):
        if value is None: return None
        exact=Decimal(str(value)).quantize(Decimal("0.01"))
        return exact if dialect.name=='postgresql' else format(exact,'f')
    def process_result_value(self, value, dialect):
        return Decimal(value) if value is not None else None


class LedgerLine(Base):
    __tablename__ = "ledger_lines"
    __table_args__ = (UniqueConstraint("tenant_id", "external_id", name="uq_tenant_external"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    date: Mapped[str] = mapped_column(String(20))
    account: Mapped[str] = mapped_column(String(120), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    debit: Mapped[Decimal] = mapped_column(ExactMoney())
    credit: Mapped[Decimal] = mapped_column(ExactMoney())
    description: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(100), default="csv")

class ExceptionRecord(Base):
    __tablename__ = "exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("ledger_lines.id"))
    rule: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(600))
    status: Mapped[str] = mapped_column(String(30), default="open")

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CloseTask(Base):
    __tablename__ = "close_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(100))
    due_date: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), default="todo")
