"""Canonical platform schema. V2 tables are isolated from the original demo."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Text, JSON, LargeBinary, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .models import ExactMoney
from .pqc_security import EncryptedJSON, EncryptedBinary

def now(): return datetime.now(timezone.utc)
class IntegrationMessage(Base):
    __tablename__ = 'integration_messages'
    __table_args__ = (UniqueConstraint('org_id','connection_id','event_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey('legal_entities.id'))
    connection_id: Mapped[str] = mapped_column(String(100))
    event_id: Mapped[str] = mapped_column(String(160))
    external_id: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column()
    envelope: Mapped[dict] = mapped_column(EncryptedJSON('integration_messages.envelope'))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='queued')
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str] = mapped_column(String(500), default='')
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
class IntegrationOutbox(Base):
    __tablename__ = 'integration_outbox'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey('integration_messages.id'), unique=True)
    payload: Mapped[dict] = mapped_column(EncryptedJSON('integration_outbox.payload'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
class ReconciliationPolicy(Base):
    __tablename__ = 'reconciliation_policies'
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), primary_key=True)
    max_pending_seconds: Mapped[int] = mapped_column(default=300)
    max_source_age_seconds: Mapped[int] = mapped_column(default=3600)
    reconciliation_interval_seconds: Mapped[int] = mapped_column(default=30)
    last_checked_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
class User(Base):
    __tablename__ = 'users'
    __table_args__ = (UniqueConstraint('org_id','email'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    email: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(Text)
class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
class LegalEntity(Base):
    __tablename__ = 'legal_entities'
    __table_args__ = (UniqueConstraint('org_id','code'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3))
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (UniqueConstraint('org_id','entity_id','code'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey('legal_entities.id'))
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(20))
    group_code: Mapped[str] = mapped_column(String(80))
    is_cash: Mapped[bool] = mapped_column(default=False)
class SourceRecord(Base):
    __tablename__ = 'source_records'
    __table_args__ = (UniqueConstraint('org_id','entity_id','connection_id','external_id','version'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(String(36))
    connection_id: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict] = mapped_column(EncryptedJSON('source_records.payload'))
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Journal(Base):
    __tablename__ = 'journal_entries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey('legal_entities.id'))
    source_id: Mapped[str] = mapped_column(ForeignKey('source_records.id'), unique=True)
    external_id: Mapped[str] = mapped_column(String(160))
    posting_date: Mapped[str] = mapped_column(String(10))
    transaction_date: Mapped[str|None] = mapped_column(String(10),nullable=True)
    period: Mapped[str|None] = mapped_column(String(7),nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    description: Mapped[str] = mapped_column(String(500))
    supersedes_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
class JournalLine(Base):
    __tablename__ = 'journal_entry_lines'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    journal_id: Mapped[str] = mapped_column(ForeignKey('journal_entries.id'))
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'))
    debit: Mapped[Decimal] = mapped_column(ExactMoney())
    credit: Mapped[Decimal] = mapped_column(ExactMoney())
    reference: Mapped[str] = mapped_column(String(160), default='')
class Finding(Base):
    __tablename__ = 'integrity_findings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    journal_id: Mapped[str] = mapped_column(String(36))
    rule: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='open')
class PlatformEvent(Base):
    __tablename__ = 'platform_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(EncryptedJSON('platform_events.detail'))
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Evidence(Base):
    __tablename__ = 'evidence_documents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    journal_id: Mapped[str] = mapped_column(ForeignKey('journal_entries.id'))
    filename: Mapped[str] = mapped_column(String(200))
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(EncryptedBinary('evidence_documents.content'))
    uploaded_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class PlatformTask(Base):
    __tablename__ = 'platform_close_tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(String(36))
    due_date: Mapped[str] = mapped_column(String(10))
    period: Mapped[str] = mapped_column(String(7))
    depends_on: Mapped[list] = mapped_column(EncryptedJSON('platform_close_tasks.depends_on'), default=list)
    status: Mapped[str] = mapped_column(String(20), default='todo')
class Proposal(Base):
    __tablename__ = 'journal_proposals'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(String(36))
    submitted_by: Mapped[str] = mapped_column(String(36))
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(String(500))
    journal_payload: Mapped[dict] = mapped_column(EncryptedJSON('journal_proposals.journal_payload'))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    decision_note: Mapped[str] = mapped_column(String(500), default='')
class BankTransaction(Base):
    __tablename__ = 'bank_transactions'
    __table_args__ = (UniqueConstraint('org_id','entity_id','external_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(String(36))
    external_id: Mapped[str] = mapped_column(String(160))
    date: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(ExactMoney())
    reference: Mapped[str] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3))
class ReconciliationMatch(Base):
    __tablename__ = 'reconciliation_matches'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    bank_id: Mapped[str] = mapped_column(ForeignKey('bank_transactions.id'), unique=True)
    line_id: Mapped[str] = mapped_column(ForeignKey('journal_entry_lines.id'), unique=True)
    matched_by: Mapped[str] = mapped_column(String(36))
class PaymentSchedule(Base):
    __tablename__ = 'payment_schedules'
    __table_args__ = (UniqueConstraint('org_id','entity_id','reference'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(String(36))
    reference: Mapped[str] = mapped_column(String(160))
    due_date: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(ExactMoney())
    direction: Mapped[str] = mapped_column(String(10))
class AnalysisRun(Base):
    __tablename__ = 'analysis_runs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str] = mapped_column(String(36))
    inputs: Mapped[dict] = mapped_column(EncryptedJSON('analysis_runs.inputs'))
    output: Mapped[dict] = mapped_column(EncryptedJSON('analysis_runs.output'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class ERPConnection(Base):
    __tablename__ = 'erp_connections'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(30))
    config: Mapped[dict] = mapped_column(EncryptedJSON('erp_connections.config'))
    credential_env: Mapped[str] = mapped_column(String(100))
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='configured')
class SyncJob(Base):
    __tablename__ = 'sync_jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    connection_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default='queued')
    attempts: Mapped[int] = mapped_column(default=0)
    checkpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict] = mapped_column(EncryptedJSON('sync_jobs.result'), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# Composite references enforce matching organization IDs at the storage boundary.
from sqlalchemy import ForeignKeyConstraint, event
for model in (User,LegalEntity,Account,SourceRecord,Journal,JournalLine,Finding,Evidence,PlatformTask,Proposal,BankTransaction,ReconciliationMatch,PaymentSchedule,AnalysisRun,ERPConnection,SyncJob):
    model.__table__.append_constraint(UniqueConstraint('org_id','id'))
for model,column,target in [
    (LegalEntity,'parent_id',LegalEntity),(Account,'entity_id',LegalEntity),
    (SourceRecord,'entity_id',LegalEntity),(Journal,'entity_id',LegalEntity),
    (Journal,'source_id',SourceRecord),(Journal,'supersedes_id',Journal),
    (JournalLine,'journal_id',Journal),(JournalLine,'account_id',Account),
    (Finding,'journal_id',Journal),(Evidence,'journal_id',Journal),
    (Evidence,'uploaded_by',User),(PlatformTask,'entity_id',LegalEntity),
    (PlatformTask,'owner_id',User),(Proposal,'entity_id',LegalEntity),
    (Proposal,'submitted_by',User),(Proposal,'reviewed_by',User),
    (BankTransaction,'entity_id',LegalEntity),(ReconciliationMatch,'bank_id',BankTransaction),
    (ReconciliationMatch,'line_id',JournalLine),(ReconciliationMatch,'matched_by',User),
    (PaymentSchedule,'entity_id',LegalEntity),(AnalysisRun,'actor_id',User),
    (ERPConnection,'entity_id',LegalEntity),(SyncJob,'connection_id',ERPConnection)]:
    model.__table__.append_constraint(ForeignKeyConstraint(['org_id',column],[target.__tablename__+'.org_id',target.__tablename__+'.id']))

def immutable_record(mapper,connection,target):
    raise ValueError('Historical financial facts and evidence are append-only; create a revision instead')
for model in (SourceRecord,Journal,JournalLine,PlatformEvent,Evidence,AnalysisRun):
    event.listen(model,'before_update',immutable_record)
    event.listen(model,'before_delete',immutable_record)

from sqlalchemy import Index
Index('uq_active_sync_connection',SyncJob.org_id,SyncJob.connection_id,unique=True,
      sqlite_where=SyncJob.status.in_(['queued','running']),
      postgresql_where=SyncJob.status.in_(['queued','running']))

class BudgetLine(Base):
    __tablename__='budget_lines'
    __table_args__=(UniqueConstraint('org_id','entity_id','period','account_id','version'),ForeignKeyConstraint(['org_id','entity_id'],['legal_entities.org_id','legal_entities.id']),ForeignKeyConstraint(['org_id','account_id'],['accounts.org_id','accounts.id']))
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    org_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    entity_id: Mapped[str]=mapped_column(String(36))
    period: Mapped[str]=mapped_column(String(7))
    account_id: Mapped[str]=mapped_column(String(36))
    version: Mapped[int]=mapped_column(default=1)
    amount: Mapped[Decimal]=mapped_column(ExactMoney())
    created_by: Mapped[str]=mapped_column(String(36))

class PeriodControl(Base):
    __tablename__='period_controls'
    __table_args__=(UniqueConstraint('org_id','entity_id','period'),ForeignKeyConstraint(['org_id','entity_id'],['legal_entities.org_id','legal_entities.id']))
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    org_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'))
    entity_id: Mapped[str]=mapped_column(String(36))
    period: Mapped[str]=mapped_column(String(7))
    status: Mapped[str]=mapped_column(String(20),default='open')
    submitted_by: Mapped[str|None]=mapped_column(String(36),nullable=True)
    reviewed_by: Mapped[str|None]=mapped_column(String(36),nullable=True)
    note: Mapped[str]=mapped_column(Text,default='')

class GroupElimination(Base):
    __tablename__='group_elimination_proposals'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    org_id: Mapped[str]=mapped_column(ForeignKey('organizations.id'),index=True)
    source_run_id: Mapped[str]=mapped_column(ForeignKey('analysis_runs.id'))
    submitted_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    reviewed_by: Mapped[str|None]=mapped_column(String(36),nullable=True)
    reason: Mapped[str]=mapped_column(String(500))
    status: Mapped[str]=mapped_column(String(20),default='pending')
    decision_note: Mapped[str]=mapped_column(String(500),default='')
GroupElimination.__table__.append_constraint(ForeignKeyConstraint(['org_id','source_run_id'],['analysis_runs.org_id','analysis_runs.id']))
GroupElimination.__table__.append_constraint(ForeignKeyConstraint(['org_id','submitted_by'],['users.org_id','users.id']))
GroupElimination.__table__.append_constraint(ForeignKeyConstraint(['org_id','reviewed_by'],['users.org_id','users.id']))
event.listen(BudgetLine,'before_update',immutable_record)
event.listen(BudgetLine,'before_delete',immutable_record)
event.listen(IntegrationOutbox,'before_update',immutable_record)
event.listen(IntegrationOutbox,'before_delete',immutable_record)
