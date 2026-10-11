"""Conservative close diagnostics; never posts journals or locks a period."""
from sqlalchemy import select
from .platform_models import *
from .auth import scoped
from . import finance_engine as finance, anti_entropy

GUIDANCE = {
    'ledger': ('Financial Reporting', 'Import balanced journals and verify opening balances and account mappings.'),
    'tasks': ('Financial Close', 'Create the period checklist and complete its tasks in dependency order.'),
    'findings': ('Data Accuracy', 'Investigate the flagged journals and record a supported resolution.'),
    'events': ('Event Reconciliation', 'Process queued events; correct failed events and reconcile version gaps with the source.'),
    'sync': ('ERP Integration', 'Finish queued imports and investigate running, failed or dead-letter jobs.'),
    'proposals': ('Financial Close', 'Ask an independent controller to review pending adjustment proposals.'),
    'bank': ('Financial Close', 'Review unmatched bank transactions and confirm supported ledger matches.'),
    'evidence': ('Audit Automation', 'Attach supporting documents to the listed active journals.'),
    'coverage': ('Event Reconciliation', 'Obtain authoritative manifests for every known source and compare them with imported records.'),
    'freshness': ('Event Reconciliation', 'Refresh stale source manifests and investigate divergent records before review.'),
}

def assess(db, actor, entity_id, period):
    scoped(db, LegalEntity, entity_id, actor)
    _, end = finance.period_dates(period)
    report = finance.statements(db, actor.org_id, entity_id, period)
    journal_ids = set(report['journal_ids'])
    def rows(model):
        return db.scalars(select(model).where(model.org_id == actor.org_id)).all()
    tasks = [r for r in rows(PlatformTask) if r.entity_id == entity_id and r.period == period]
    findings = [r.id for r in rows(Finding) if r.journal_id in journal_ids and r.status == 'open']
    pending = [r.id for r in rows(IntegrationMessage) if r.entity_id == entity_id and r.status != 'applied']
    proposals = [r.id for r in rows(Proposal) if r.entity_id == entity_id and r.status == 'pending' and r.journal_payload.get('posting_date', '') <= end]
    matched = {r.bank_id for r in rows(ReconciliationMatch)}
    bank = [r.id for r in rows(BankTransaction) if r.entity_id == entity_id and r.date <= end and r.id not in matched]
    evidence = {r.journal_id for r in rows(Evidence)}
    missing_evidence = sorted(journal_ids - evidence)
    connections = {r.connection_id for r in rows(SourceRecord) if r.entity_id == entity_id}
    connections |= {r.id for r in rows(ERPConnection) if r.entity_id == entity_id}
    sync_jobs = [r.id for r in rows(SyncJob) if r.connection_id in connections and r.status != 'complete']
    observations = {r['connection_id']: r for r in anti_entropy.freshness(db, actor)['sources'] if r['entity_id'] == entity_id}
    unverified = sorted(c for c in connections if c not in observations)
    unhealthy = sorted(c for c in connections if c in observations and (observations[c]['stale'] or not observations[c]['converged']))
    checks = []
    def check(code, label, passed, affected):
        module, remedy = GUIDANCE[code]
        checks.append({'code': code, 'label': label, 'passed': bool(passed), 'affected_ids': sorted(affected), 'module': module, 'remedy': remedy if not passed else 'No action required for this check.'})
    check('ledger', 'Balanced ledger with imported activity', bool(journal_ids) and report['balance_check'] == '0.00', sorted(journal_ids))
    check('tasks', 'Period checklist exists and is complete', bool(tasks) and all(r.status == 'complete' for r in tasks), [r.id for r in tasks if r.status != 'complete'])
    check('findings', 'No open findings on active books', not findings, findings)
    check('events', 'All received entity events applied', not pending, pending)
    check('sync', 'Known source import jobs completed', not sync_jobs, sync_jobs)
    check('proposals', 'No pending adjustments through period end', not proposals, proposals)
    check('bank', 'Imported bank transactions through period end matched', not bank, bank)
    check('evidence', 'Evidence attached to every active journal through period end', not missing_evidence, missing_evidence)
    check('coverage', 'Every known source has a manifest observation', bool(connections) and not unverified, unverified)
    check('freshness', 'Known source manifests are current and converged', bool(connections) and not unverified and not unhealthy, sorted(set(unhealthy + unverified)))
    return {'entity_id': entity_id, 'period': period, 'checked_at': now().isoformat(), 'ready_for_review': all(c['passed'] for c in checks), 'checks': checks, 'blockers': [c['code'] for c in checks if not c['passed']], 'basis': 'Point-in-time checks of imported records and known sources. Unknown sources, external bank completeness and opening balances require independent verification. This is not a period lock or approval.'}

