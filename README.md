# AI Finance OS — Platform Development Release 0.6.1

A larger implementation of the eight-module blueprint in the supplied notes. React/Vite workspace, FastAPI services, a canonical relational accounting model, exact decimal arithmetic, password authentication with server-derived organization scope, restricted investigation adapters, and controlled review workflows.

## Start locally on Windows

Requirements: Python 3.12+ and Node 22+. Run `Start-Finance.ps1` from this folder. It creates an isolated Python environment, installs dependencies, starts API/dashboard background processes, and records logs under `.runtime`. Open http://localhost:5173. Use `Stop-Finance.ps1` to stop its recorded processes.

Create your organization in the dashboard. Then select **Load example workspace** on Overview. This creates two synthetic legal entities, account mappings, seven balanced journals, a duplicate finding, bank data, cash schedules and dependent close tasks. Create a second controller in Organization to test independent approvals. The sample duplicate intentionally overstates revenue until a source revision or approved correction is prepared.

Manual startup in two terminals:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Local SQLite database: `backend/finance-platform.db`. The previous demo database is retained separately. Earlier demo APIs are source-only in `app/legacy_main.py`; the current API exposes authenticated platform workflows.

## PostgreSQL deployment configuration

Copy `.env.example` to `.env` and provide a long URL-safe random `FINANCE_DB_PASSWORD`. With Docker Desktop installed:

```powershell
docker compose up --build
```

Compose provides PostgreSQL 16, a persistent volume, a health check, Alembic baseline migration, the API and dashboard. API and dashboard ports bind only to loopback. PostgreSQL monetary columns use NUMERIC(20,2); SQLite stores exact decimal text. Docker/PostgreSQL configuration must be validated in your deployment environment before use.

## Developed workflows

| Module | Implemented scope |
|---|---|
| Financial Close | Tasks, owners, dependency gates, exact bank matching, independent journal proposal review |
| ERP Integration | Read-only Business Central and NetSuite transport adapters, page staging, source retention, retries, checkpoints, dead-letter states |
| Financial Reporting | Mapped P&L, balance sheet, trial balance, period variance, versioned budgets, CSV/Excel/PDF snapshots |
| Audit Automation | Hashed documents, journal linkage, evidence gaps, export packages, actor-attributed event hash chain |
| Cash Intelligence | Thirteen-week scheduled-payment forecasts, collection delays, inflow/outflow scenarios, versioned run snapshots |
| Data Accuracy | Balanced journals, explicit mappings, exact amounts, duplicate hypotheses, sequential revisions, source hashes and lineage |
| Legacy Modernization | CSV schema discovery, field mappings, deterministic transformation preview, original extract archival |
| Consolidation | Entity hierarchy, group account mappings, supplied FX translation, reciprocal intercompany matching, independent elimination proposals |

Group reports can apply selected independently approved eliminations. They reject stale source snapshots and overlapping claims. This does not implement statutory ownership accounting, non-controlling interests, CTA, or historical equity translation.

## ERP and AI configuration

See `docs/CONNECTORS.md`. Live provider accounts have not been accessed. Transport and workflow tests use mock responses. A successful mock is not proof that an account-specific ERP mapping works in production.

For optional model investigations, configure `OPENAI_API_KEY` and `OPENAI_MODEL` in the API environment. The model receives only scoped journal and evidence metadata; it cannot calculate accounting reports, post, approve or execute arbitrary SQL. Responses use a strict schema, and unavailable evidence IDs are rejected. Without credentials, Rules investigations remain available and are explicitly labeled.

## Checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
```

```powershell
cd frontend
npm run build
```

See `docs/VERIFICATION.md` for actual results and untested environments, and `docs/REQUIREMENTS-COVERAGE.md` for the boundary between delivered functionality and remaining blueprint work.

This is a development release. SSO/MFA, independent security assessment, database row-level read policies, immutable external evidence storage, distributed workflow orchestration, production connector certification and disaster recovery exercises remain work before an enterprise pilot.

## Event reconciliation extension

Durable inbox, ordered projection, hash-based replay checks, tombstones, explicit restoration, transactional local outbox, backlog monitoring and retry/dead-letter states are implemented. See docs/EVENT-PIPELINE.md for contracts and production gaps. Use Start-Finance.ps1 -WebPort 5174 when 5173 is occupied; -SkipInstall reuses installed dependencies.


## Source freshness and anti-entropy

Configure delay thresholds and compare authoritative source manifests in Event Reconciliation. The launcher runs a background worker; freshness distinguishes queue completion from upstream observation. See docs/ANTI-ENTROPY.md for API contracts, exact comparison scope and deployment limitations.


## Customer-data security update

Encryption keys are required by default. After dependencies are installed, run backend/.venv/Scripts/python.exe -m app.security_admin init from backend before first launch. Run app.security_admin migrate offline for an existing local database. Keys stay outside the project. See docs/PQC-SECURITY.md for protection boundaries, managed-key/TLS deployment and trust-pinned audit verification. This local release is not certified for customer production.



Close readiness: Financial Close checks imported books and known-source manifests, with encrypted immutable review snapshots. See [CLOSE-READINESS.md](docs/CLOSE-READINESS.md).


Cash Intelligence now includes saved-forecast reliability review against imported bank movements. See [cash review](docs/CASH-REVIEW.md).

Treasury stress testing is available in Cash Intelligence; see [treasury stress lab](docs/TREASURY-STRESS.md).

Organization now provides self-service session review and revocation. See [session security](docs/SESSION-SECURITY.md).

Receivables collection review is available in Cash Intelligence. See [collection monitor](docs/COLLECTION-MONITOR.md).

Cash Intelligence includes [reverse liquidity stress testing](docs/LIQUIDITY-LIMITS.md).

Executive Briefing provides organization-wide close, collection and historical treasury review with currencies shown separately. Market feeds, valuations and investment recommendations are outside this feature.

Financial Reporting includes a [CFO budget exception monitor](docs/CFO-BUDGET-MONITOR.md) using organization-specific account mappings and materiality thresholds.

Financial Reporting includes a CFO review change tracker for two saved budget-exception reviews. It compares frozen values and policy thresholds, rather than current ledger state. Select an earlier and later review for the same entity and period. The picker uses the most recent 100 organization analysis runs supplied by /runs.
