# ERP connector setup and contracts

Both adapters are read-only. No production vendor account was used in development. Validate balances and source completeness against your own ERP before a pilot.

## Secret isolation

After creating an organization, use a deployment variable named:

`FINANCE_SECRET_<ORGANIZATION_UUID_WITHOUT_DASHES_IN_UPPERCASE>_<NAME>`

The API checks that a connection references its own organization's prefix. Credentials are not accepted in connection JSON and are never returned. Supply the variable to the API/worker process, or add it to your local `.env` and start uvicorn with `--env-file ../.env`. Docker requires an operator-provided environment override to inject each organization's secret; the generic compose file intentionally does not enumerate tenant secrets.

## Business Central

Connection config:

```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000000",
  "company_id": "00000000-0000-0000-0000-000000000000",
  "environment": "Production",
  "account_mapping": {"10000":"1000", "40000":"4000"}
}
```

Use real Entra tenant/company IDs. The secret variable can contain a bearer access token, or JSON with `client_id` and `client_secret`. Client credentials obtain a token using the Business Central `.default` scope. The application must have the appropriate tenant/company permissions.

The adapter retrieves API v2.0 `generalLedgerEntries`, validates continuation URLs against the configured provider/company path, and groups debit/credit entries by posting date and document number. Document numbers are not guaranteed to uniquely identify accounting transactions in every configuration. Validate this grouping contract for each account. Incomplete documents fail balancing checks; the service never invents a balancing line. Amounts are interpreted as signed debit/credit values in the entity's functional currency.

Official reference: [GET generalLedgerEntries](https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_generalledgerentry_get).

## NetSuite

Connection config:

```json
{
  "account_id": "123456-sb1",
  "query_env": "FINANCE_QUERY_MY_NETSUITE_LEDGER",
  "account_mapping": {"source-account-id":"1000"}
}
```

Use the REST-compatible account hostname. The organization-specific secret contains a SuiteTalk OAuth bearer token. The query environment variable contains a single SELECT validated by the deployment operator. It must return these aliases: `external_id`, `posting_date` (YYYY-MM-DD), `account_code`, `debit`, `credit`; optional `description`, `reference`. Each external ID must describe a complete balanced journal in the selected entity's functional currency. Configure subsidiary, posting book, journal scope and permissions explicitly in the query. The application does not claim a universal query fits every NetSuite schema.

The adapter sends SuiteQL requests with `Prefer: transient` and offset pagination. Bearer-token lifecycle/rotation must be managed externally; account-specific OAuth provisioning is not automated.

Official reference: [Executing SuiteQL through REST](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_157909186990.html).

## Sync lifecycle

Configure a connection, queue a job, then Advance/retry in the UI, or run `python -m app.worker` from backend with the same deployment environment. `--once` processes one sweep. Use a single worker for this development release.

Each page is retained in the job's source archive with a durable checkpoint. All pages are staged before normalization/import. The final source archive receives a hash and transform version. Journal imports and completion checkpoints commit together. Conflicts and normalization failures roll back financial changes. A job is dead-lettered after three failed steps; create a new job after correcting the cause. Transient provider responses receive three bounded transport attempts.

Current implementation refreshes bounded snapshots; it does not yet offer provider-specific incremental watermarks, webhook renewal, a distributed scheduler, rate-limit metrics, or encrypted credential-vault integration. Repeated snapshots are idempotent; changed journals create sequential versions under controller authority.

## Controlled AI adapter

Set `OPENAI_API_KEY` and an account-accessible `OPENAI_MODEL`. The Responses API call uses `store:false`, no execution tools, a strict JSON schema and a bounded output limit. Only pre-authorized journal data and document metadata are sent. The returned evidence IDs must exist in that scoped request. Runs record the model, request/response identifier, usage counts, inputs and output; cost reporting requires billing integration. The rules provider works without a model key.

Official reference: [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
