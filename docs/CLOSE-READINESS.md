# Close readiness

Financial Close now offers **Check readiness** and a controller-only **Save audit snapshot** for the selected entity and period.

Ten conservative checks cover imported activity and ledger balance, the period checklist, open findings, unresolved entity events, unfinished ERP import jobs, pending adjustments, unmatched imported bank records, journal evidence, known-source manifest coverage, and current manifest convergence. Journal, evidence, finding, bank and proposal checks include activity through period end because prior-period records affect the balance sheet. Unresolved events and source freshness are checked across the entity because changes can affect historical balances.

An empty ledger or missing checklist does not pass. Every source represented in imported records or configured ERP connections needs a current, converged manifest. Manifest observations remain controller-supplied; the platform cannot discover an omitted external source. Receipt and bank completeness, opening balances, and authenticity still need independent verification.

GET `/close/readiness?entity_id=...&period=YYYY-MM` recomputes the current state for authenticated organization members. POST `/close/readiness` with the same entity and period saves an immutable `close_readiness` analysis run and audit event; only owners/controllers can save it. Snapshots use the existing encrypted analysis storage when encryption is enabled. They remain available under Runs and Investigation history. A snapshot records the checks at its timestamp; it is not continuously updated, a period lock, an independent approval, or statutory certification. Refresh after changes.

Validation: 43 backend tests pass, including empty-data blocking, tenant boundaries, role restrictions, and readiness invalidation after a source revision while retaining the historical snapshot.


Each check now includes a suggested next action and module navigation. Expand affected records to inspect exact identifiers. Historical incomplete import jobs conservatively remain blockers even if a later job succeeds; investigate their state rather than silently assuming recovery.

Signed snapshot export: after saving, Download signed snapshot creates a ZIP with close-readiness.json and an ML-DSA-65 receipt binding the file's SHA-512 digest. The existing security_admin verify command can validate it against the separately pinned signing public key. Exports require initialized keys, enforce organization scope, and record an audit event. Authorized downloads contain plaintext financial metadata: share only with intended reviewers. This signature proves integrity against the trusted key, not accounting correctness.

Saved close reports: load historical snapshots for the selected entity and period, view their original assessment and download a signed report. Saving a snapshot refreshes the history. Historical checks are not current close approval.
