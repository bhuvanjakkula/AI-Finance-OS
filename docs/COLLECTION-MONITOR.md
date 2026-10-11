# Receivables collection monitor — 11 October 2026

Cash Intelligence now includes a read-only collection review. Select a review date to compare current expected inflow schedules with imported same-entity, same-currency bank movements dated through that day. Exact, case-sensitive reference matches supply receipt evidence. Negative same-reference amounts reduce net receipts; evidence credited to a schedule is bounded between zero and its expected amount. Excess receipts are separately shown.

The monitor displays outstanding/overdue estimates, five aging buckets, partial collection evidence, source bank IDs, unlinked positive receipts and the share of outstanding amounts represented by the largest five schedules. Rows are sorted by outstanding amount, then overdue days. Due today is classified as not overdue. Outflow schedules are excluded.

GET /cash/collections?entity_id=ID&as_of=YYYY-MM-DD requires authenticated organization access; auditors may read. Future dates are rejected. No schema migration, external provider or accounting write is required.

Limits: payment schedules are current records, not historical as-of snapshots. References are assumed to designate a schedule; merged remittances, misused references and multiple invoices require human allocation. The monitor does not certify bank completeness, invoice settlement or receivables balances, and does not infer customer concentration from schedule references. It does not send collection messages.

Verification: 51 backend tests pass; production build passes. Tests cover partial receipts, refunds, overpayment, aging, future bank records, unlinked records, outflow exclusion, auditor access and invalid/foreign entity requests. Browser verified a synthetic 25,000 USD receipt as two days overdue without matching bank evidence and separately flagged one unlinked positive bank record.
