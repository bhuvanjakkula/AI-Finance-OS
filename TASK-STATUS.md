# Finance project task status — 9 October 2026

Overall: the local development platform is implemented and running. The enterprise blueprint is not fully complete. Release 0.5.1 corrects gaps found during the audit of the 8 October requests and current source/backlog.

| Request or work item | Status and evidence |
|---|---|
| Build from starter ZIP and expand using original finance notes | Implemented development workflows for eight modules with canonical accounting, exact money, authentication, role checks and independent adjustment approval. Scope limits remain in docs/REQUIREMENTS-COVERAGE.md. |
| Universal ERP integration | Canonical import, CSV mapping, read-only Business Central/NetSuite adapters and bounded staged snapshot sync implemented; providers are tested with mocks. Live source certification remains blocked by credentials and provider data. |
| Event-driven ingestion / CDC / message queuing | Durable local inbox, sequential projection, checkpoint-like source versions, savepoints and transactional local outbox implemented. Live CDC subscriptions and an external broker publisher/consumer remain engineering and deployment work. |
| Idempotency / deduplication / provenance | Envelope and source hash checks, persistent replay identities, immutable source history and review-only duplicate hypotheses implemented and tested. Financial amounts are not automatically merged using CRDTs. |
| Tombstones / lifecycle consistency | Persistent deletion markers, active-report exclusion, retained history, accidental resurrection prevention and explicit controller restore implemented and tested. Retention/purge policy is not automated. |
| Anti-entropy / staleness bounds | Exact bounded source-manifest comparison, dynamic divergence checks, configurable pending/source-age thresholds and policy-driven background checks implemented. This does not implement gossip, rateless transport, quorum replicas or PBS latency guarantees. |
| Show populated dashboard | Opened and signed into the existing synthetic local QA workspace; Overview shows two entities, seven journals, one finding and two unfinished sample close tasks. Sample findings/tasks are demo business records, not failed software tasks; no evidence or independent review was fabricated to clear them. |
| Fair event processing | Completed today: more than 100 blocked streams cannot prevent an unrelated ready revision from processing. Regression test covers 110 blocked version-2 streams and a ready version-3 stream. |
| Run reconciliation in Docker | Completed configuration: worker service waits for healthy API after migrations. Docker is unavailable on this machine; actual image/Compose/PostgreSQL execution remains unverified. |
| Safe local startup | Completed: launcher checks requested ports before starting or replacing recorded process state. Recorded API/dashboard/worker restarted and verified locally. |
| Tests/build/migration/package | 37 backend tests pass; one installed Starlette TestClient deprecation warning remains. Frontend build, Alembic migration and one worker cycle pass; pip check reports no broken requirements. Updated ZIP excludes credentials, databases and installed dependencies. |

## Concrete external blockers

- Live Business Central: organization-specific Entra credentials/permissions, tenant/environment/company IDs, chart mappings and representative complete ledger extracts.
- Live NetSuite: read-only token, account-specific approved SuiteQL query, subsidiary/account mappings and representative extracts.
- Live model validation: API key, selected model configuration and labeled finance discrepancies for quality evaluation. Rules mode works locally.
- Docker/PostgreSQL rehearsal: Docker runtime is not installed/available. Config and SQL dialect checks do not prove a successful live deployment.
- Hosted deployment: target infrastructure, domain/TLS and managed database/secret/object-storage configuration have not been supplied. No public deployment was attempted.
- Statutory and commercial certification: jurisdiction/GAAP policies, finance-domain review, customer pilot data and independent security/control assessment remain necessary.

## Remaining engineering, distinct from credential blockers

The broad nine-month blueprint still includes SSO/MFA/recovery, database RLS, vault/object storage and external immutable audit anchors, live CDC/broker integration, multi-worker leases/load testing, certified source-completeness close gates, period locks, subledger matching, recurring close tasks/notifications, approved ERP posting, statistical cash calibration and actual-vs-forecast review, statutory ownership/NCI/CTA accounting, fiscal-calendar/cash-flow reporting, OCR, signed transformations, backup/restore rehearsal and production monitoring. These are not marked complete or disguised as credential-only blockers. See the coverage matrix and roadmap for boundaries.

## Execution recovery and review notes

Yesterday's UI initially showed only sign-in; this was resolved by signing into the existing local synthetic workspace, without disabling authentication. The event-screen build initially failed due to duplicated state declarations from repeated helper execution; the final source contains one state declaration and builds successfully. The new readiness query briefly failed the existing ordering regression during today's fix; that variable collision was corrected and all 37 tests pass. No applicable AGENTS.md was found in the project/workspace search.

The original starter history and research notes were reviewed as project scope/reference. Research performance percentages and clinical conflict-resolution figures were not treated as finance benchmarks or runtime guarantees. Current tests and actual code, not previous completion messages, determine this status.

## Running locally

Dashboard: http://127.0.0.1:5174/ . API: http://127.0.0.1:8000/docs . Single worker runs in the background. Stop with Stop-Finance.ps1; restart with Start-Finance.ps1 -WebPort 5174 -SkipInstall when dependencies already exist. Sessions remain tab-local and expire; signing in again is expected after a new/reloaded tab or expiry.

## Security request — 9 October

Implemented local ML-KEM encrypted JSON/evidence, offline payload migration with encrypted backup, ML-DSA signed audit packages and trust-pinned verification, restrictive local key ACLs outside OneDrive, HTTP security controls and explicit production startup prerequisites. TLS gateway is a deployment template, not running PQ transport. Scalar metadata/amounts require full storage encryption, and managed keys/rotation, SSO/MFA, production migration, RLS, WORM anchoring and independent security reviews remain pending. No claim of total protection or customer-production certification.
