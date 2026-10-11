# Requirements coverage against supplied blueprint

This is an implementation status matrix, not a claim that the 9-month enterprise program is complete.

| Blueprint area | Delivered technology | Remaining enterprise work |
|---|---|---|
| Multi-tenant authentication/RBAC | Salted scrypt password hashes, 8-hour opaque hashed sessions, server-derived organization scope, four roles, composite organization foreign keys | SSO, MFA, recovery, session administration, database RLS, distributed abuse protection |
| Entity and account foundation | Legal-entity hierarchy, functional currency, mapped account categories and group codes | Ownership percentages, chart mapping revision workflows, regional accounting policies |
| Source lineage | Sequential immutable source/journal versions, source hashes, active-version reporting, ERP raw staging and original CSV archival | External immutable object storage, residency and retention policies, signed transformations |
| Accuracy | Strict amounts/dates/currencies, account checks, balanced journals, conflicting version protection, duplicate hypotheses | Historical labeled anomaly dataset, advanced cross-system root-cause graph, materiality controls |
| NetSuite and Business Central | Read-only HTTP transports, pagination, bounded retries, shared staging/normalization workflow, credential references | Account-specific live certification, token rotation, broader transaction coverage, incremental checkpoints, webhooks |
| Legacy integration | CSV schema discovery, configurable column mapping, validated preview, original source retention | OCR, additional system-specific wrappers, learned mappings, migration reconciliation at scale |
| Reporting | Trial balance, P&L, cumulative balance sheet, monthly variance, versioned budgets, Excel/PDF/CSV, source snapshots | Fiscal-calendar policy, scheduled delivery, comparative statements, cash flow statements, certified accounting templates |
| Financial close | Calendar/tasks, owners, dependency gates, exact bank/GL candidates, controller-confirmed matches | Subledger matching, task notifications, period locks, recurring templates, full close certification |
| Approvals | Independent reviewer, conditional state transitions, actor audit, approved draft export | ERP write-back execution, signing, external approval notifications, advanced separation-of-duty policies |
| Audit | Hashed document uploads/downloads, evidence gaps, read-only auditor role, export packages, event chain verification | OCR, controls/sampling policy, malware scanning, independent WORM storage and audit assurance |
| Cash intelligence | 13-week schedule scenarios, collection delays, factors, negative-cash warnings in output, source IDs and snapshots | Live banking, probabilistic confidence, model calibration, forecast-vs-actual review |
| Intercompany/consolidation | Reciprocal claim tagging/matching, FX rate snapshots, independent elimination drafts, stale/double elimination guards, translated group trial balance | Statutory ownership/NCI, CTA, average/historical rates, minority/partial ownership, full consolidated statements |
| AI controls | Restricted Responses API adapter, strict outputs, authorized source context, evidence ID checks, run logs, daily/output limits, rejection tests | Pilot quality evaluation, provider billing/actual costs, broader agent tools, content-grounding quality metrics |
| Operations | PostgreSQL compose configuration, baseline migration, local launcher/stopper, durable sync worker, CI tests/build | Live PostgreSQL load testing, multiple workers, Temporal, monitoring/alerts, backup restoration, disaster recovery |
| Commercial readiness | Runnable demonstration workflows and technical scope documentation | Design partners, paid pilots, contracts, procurement review, finance-domain sign-off, independent security assessment |

No SOC 1/SOC 2, GDPR assurance, SLA or production reliability claim is made. The supplied notes' budget, market, pricing and launch estimates were treated as project context, not verified commercial facts.

Event reconciliation added in 0.4: durable inbox/outbox, sequential projection, persistent tombstones, restore controls, replay suppression, waiting gaps and quarantined conflicts. Live CDC capture and broker publishing remain deployment work. See EVENT-PIPELINE.md.

Version 0.5: exact bounded source manifests, missing/divergent/unexpected detection, configurable backlog/source age thresholds, policy-driven worker checks and local audit alerts. Distributed gossip, rateless set transport and probabilistic staleness guarantees remain unimplemented.

Security 0.6: encrypted platform JSON/evidence using ML-KEM-768 and AES-256-GCM, signed ML-DSA-65 audit packages, encryption-required startup, own-session revocation, HTTP hardening and PQ TLS gateway template. Scalar database encryption, managed key custody/rotation, verified TLS negotiation, production PostgreSQL migration, MFA/RLS/WORM and independent security review remain outstanding.

Cash review extension: completed-week forecast-versus-imported-bank movement errors, mean absolute net error over observed weeks, tolerance alerts, source IDs and retrospective labeling are delivered. Live banking completeness and statistical calibration remain outstanding.

Treasury stress extension: deterministic collection delays, inflow/outflow shocks, reserve breach detection, funding gap calculation and frozen-source lineage delivered. Intraweek liquidity, financing costs and statistical/market-risk models remain outstanding.

Session controls extension: self-service active-session administration, current-session labeling, domain-separated public identifiers, per-user bulk revocation and logout audit events delivered. MFA/SSO and distributed identity defenses remain outstanding.

Collection monitor extension: schedule aging and exact bank-reference receipt evidence, refunds, partial/excess collection indicators and unlinked receipt review delivered. Full invoice settlement/allocation and historical schedule snapshots remain outstanding.

Reverse liquidity extension: conservative collection-loss boundary search with reserve headroom, next-step breach and funding-gap calculations delivered. Timing shocks and probabilistic risk are not modeled by this feature.
