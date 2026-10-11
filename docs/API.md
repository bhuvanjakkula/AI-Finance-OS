# API workflow guide

Swagger schema: http://localhost:8000/docs. All business routes require `Authorization: Bearer <session token>`.

1. POST /auth/register creates an organization and owner; POST /auth/login signs in with organization slug, email and password. GET /auth/me and POST /auth/logout inspect/revoke sessions.
2. Owners create team members through POST /users. Controllers/owners create entities and account mappings through /entities and /entities/{id}/accounts.
3. POST /journals/import accepts entity_id, connection_id and balanced journals. GET /journals supports include_history; /journals/{id}/lineage returns source payload/hash and evidence.
4. /legacy/preview and /legacy/import accept multipart entity_id, JSON mapping and CSV file. Preview validates before import; import archives the source extract.
5. /reports/trial-balance, /reports/statements, /reports/variance and /reports/budget use entity_id and reporting periods. /budgets creates a sequential budget version. /reports/export.csv and /reports/export?format=xlsx|pdf download reports.
6. /integrity/findings lists findings; controllers review through /integrity/findings/{id}/review. /agents/investigate records a rules or optional OpenAI narrative with evidence references.
7. /close/tasks creates and updates scoped tasks with dependencies. /proposals creates balanced adjustment drafts; a different controller decides through /proposals/{id}/decision. /proposals/{id}/export returns an approved draft without posting.
8. /bank/import ingests signed bank records. /reconciliation returns exact candidate matches. Controllers confirm through /reconciliation/matches; one bank record and one ledger line can only participate in one match.
9. /evidence accepts a document and journal_id. Evidence list/download routes expose scoped metadata/content. /audit/gaps, /audit/package, /audit/events and /audit/verify support evidence review and chain checks.
10. /cash/payments records expected schedules; /cash/forecast computes thirteen weekly buckets from opening cash and scenario assumptions. Results are snapshots in /runs.
11. /connections configures secret references and provider settings; /connections/{id}/sync creates a job. /sync/jobs lists checkpoints. /sync/jobs/{id}/step advances one page or retries; a worker can automate steps.
12. /intercompany/runs computes exact reciprocal matches using IC:COUNTERPARTY_CODE:REFERENCE tags. /consolidation/elimination-proposals drafts adjustments; /{id}/decision records independent review. /consolidation/runs applies selected approved_elimination_ids only if group, period, rates and current source snapshot agree.

HTTP 401 means sign-in/session failure; 403 means an authorization or independent-review gate; 404 conceals records outside the organization; 409 means state/version conflict; 422 means input or accounting validation failure. A failed multi-journal import rolls back the entire batch. Sync failures preserve earlier staged pages while rolling back financial inserts.

Close readiness: GET /close/readiness?entity_id=...&period=YYYY-MM recomputes known-source and financial checks; POST /close/readiness saves a controller-owned immutable AnalysisRun (201). Both are tenant scoped; POST requires owner/controller.
