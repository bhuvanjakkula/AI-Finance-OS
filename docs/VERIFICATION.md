# Verification — 8 October 2026

Backend: 37 tests passed in an isolated project virtual environment (Python 3.14). One installed Starlette test-client deprecation warning remains. `pip check` found no broken dependency requirements. The tested environment is recorded in backend/requirements.lock.txt.

Coverage includes original starter regressions plus authenticated organization scope, forged tenant headers, auditor permissions, database cross-organization foreign keys, exact journal arithmetic, whole-batch rollback, source revision lineage, separate transaction/posting dates, mapped statement golden data, independent approvals, close dependency gates, exact bank matching, evidence export, chain tampering, cash scenarios, budget revisions, reciprocal intercompany matching, stale elimination rejection, structured AI citation rejection, mocked provider pagination, and staged sync idempotency.

Frontend: production Vite build passed. Browser checks created a synthetic local organization, loaded the two-entity sample, inspected mapped P&L/balance sheet values and completed a rule-based discrepancy investigation. The browser's narrow viewport exercised the responsive layout. No real user credentials, ERP or model provider were used.

Migration: Alembic baseline and source-date migration applied successfully to local SQLite; current revision 0004_reconciliation_policy. PostgreSQL NUMERIC DDL and exact Decimal binding are tested by dialect compilation. A live PostgreSQL instance and Docker build were not available and were not tested. Windows launcher scripts were parsed but not executed end-to-end.

ERP and model tests use MockTransport or fake adapters. Live OAuth scopes, subsidiary/account mappings, complete journal grouping, provider availability and model narrative quality require customer credentials and domain validation. Excel files are opened by openpyxl tests; PDF export signatures and snapshot linkage are checked. PDF output has not received page-by-page visual review.

Event pipeline: ordered waiting/recovery, replay hash conflicts, deletion/restore lifecycle, retained history, validation dead letters, role restrictions and atomic outbox projection are covered. Event screen is build-verified; no live CDC source, distributed broker or multi-node performance test was run.

Event pipeline: ordered waiting/recovery, replay hash conflicts, deletion/restore lifecycle, retained history, validation dead letters, role restrictions and atomic outbox projection are covered. Event screen is build-verified; no live CDC source, distributed broker or multi-node performance test was run.

Event pipeline: ordered waiting/recovery, replay hash conflicts, deletion/restore lifecycle, retained history, validation dead letters, role restrictions and atomic outbox projection are covered. Event screen is build-verified; no live CDC source, distributed broker or multi-node performance test was run.

Version 0.5 tests cover exact manifest differences, historical-observation invalidation after revision, stale source/pending thresholds, controller permissions, input bounds and due-worker cadence. The local launcher starts a worker. Manifest UI is build-verified; live upstream anti-entropy transport is not tested.


9 October audit (0.5.1): blocked-stream fairness regression passes with 110 gaps; all 37 tests pass. Dashboard login, live backlog and local manifest inspection were browser-verified with synthetic data. Docker worker configuration was added but Docker is unavailable for runtime verification. Launcher port preflight and local API/web/worker restart succeeded. See TASK-STATUS.md.


Security release 0.6 (9 October): 41 tests pass, including real ML-KEM envelope roundtrip/tamper/context checks, native ML-DSA signatures and trust-key rejection, raw encrypted database inspection, signed package verification, security headers/host/body guards, session revocation and production startup rejection. Local migration encrypted 22 JSON rows (no evidence documents existed). Encrypted backup recovery in memory verified all seven source records; a live synthetic audit package signature and member digests verified. Vite was updated to 6.4.4 with patched Rollup/esbuild; npm audit reports zero known vulnerabilities. TLS gateway configuration is unexecuted; no end-to-end PQ TLS or production certification is claimed.

Backend pip-audit also reports no known vulnerabilities; this is an advisory scan, not penetration testing or crypto review.
The final built dashboard uses a same-origin /api proxy and at most three parallel reads. Browser verification completed Overview and mapped P&L/balance sheet after encryption, with no fetch error. Launcher and Docker web serve built preview assets; production requires the TLS/static gateway deployment.

Release 0.6.1: 43 backend tests pass; frontend production build passes. Close-readiness snapshot save verified in the local browser against synthetic records; six unmet checks correctly prevent a ready-for-review result. See CLOSE-READINESS.md.

Guided close update: 44 tests pass; production build passes. Browser verified next-step guidance, affected record controls, and navigation from a finding blocker to Data Accuracy. Failed import jobs are blockers until complete.

Signed close export: 45 tests pass, including signature verification and SHA-512 content binding; frontend build passes and the download control was verified in the synthetic dashboard.

11 October completion audit: 46 backend tests pass (one existing Starlette/httpx deprecation warning); frontend build passes. Saved-close history refresh and empty-state guidance added. API/web/worker started successfully; HTTP health checks passed. Browser loaded two historical snapshots in the existing synthetic QA workspace. Live ERP/production environments remain unverified.

Cash reliability review (11 October): 47 tests pass; production build passes. Browser verified frozen-scenario selection, retrospective warning and exclusion of incomplete weeks. See CASH-REVIEW.md.

Treasury stress lab (11 October): 48 tests pass, frontend build passes; five-scenario run saved and browser-verified with synthetic data. See TREASURY-STRESS.md for modeling boundaries.

Session management (11 October): 50 tests pass and frontend build passes. Browser verified listing/current-session identification and bulk revocation in the synthetic QA account. See SESSION-SECURITY.md for API changes and limits.

Collection monitor (11 October): 51 tests pass; build passes. Exact receipt/reference evidence, aging, refunds and role/tenant scope tested. Synthetic dashboard verified overdue and unlinked records. See COLLECTION-MONITOR.md.

Reverse liquidity stress (11 October): 53 tests pass; build passes. Boundary, funding, opening deficit and zero-collection cases verified. Synthetic browser workflow saved a 51.20% collection-loss limit. See LIQUIDITY-LIMITS.md.

PQC verifier hardening (11 October): 60 tests pass with one existing deprecation warning; frontend build passes and API schema returns HTTP 200 after restart. Real ML-DSA signed archives verify; modified content, unsafe paths and unsigned receipt fields are rejected. Large test payloads exercise streaming reads. Existing key formats and encrypted data remain unchanged.

Executive Briefing (11 October): 61 tests pass; production build passes. Browser verified USD/EUR separation, missing scenario labels, current close blockers and historical stress/limit summaries in the synthetic organization.

CFO budget monitor (11 October): 62 tests pass; production build passes. Live synthetic dashboard flagged two material unbudgeted accounts and saved the review. See CFO-BUDGET-MONITOR.md.

CFO review change tracker (11 October): 63 tests pass; frontend build passes. Tests cover frozen actual changes, threshold disclosure, identity/order validation and read access. Browser compared two synthetic reviews with unchanged actuals but a changed materiality threshold, correctly showing the changed review flag.

Foundation controls: 64 tests pass in the initial run; live encrypted SQLite backup recovered and integrity-checked in memory with 29 tables. Frontend build passed. Later-close backdated guards received an additional test run; PostgreSQL concurrency and live independent finance review remain untested.

OpenAI readiness: 65 tests pass; frontend build passes. Authenticated status is verified locally without exposing API keys; existing mocked adapter tests cover structured outputs and rejected invalid evidence. No live OpenAI call was made.

Passwordless owner mode: 66 tests pass; frontend build passes; browser opened owner workspace without entering credentials. Mode requires explicit configuration, loopback client and local origin, rejects cross-site requests and is blocked in production.
