# Security implementation and operational requirements

## Implemented boundaries

- Organization scope is derived from hashed bearer sessions, never a client tenant ID.
- Salts and scrypt protect password hashes. Session tokens expire after eight hours and are revocable at logout.
- Roles control writes, member creation, account configuration and consequential review.
- Independent-review rules prevent both journal and group-elimination submitters from deciding their own proposals.
- Composite foreign keys reject cross-organization references. Tests cover API and database isolation.
- Credentials live in deployment variables with an organization-specific namespace; no API receives raw connector secrets.
- Provider pagination remains on the configured HTTPS endpoint, redirect following is disabled, and transport retries are bounded.
- Financial/source/evidence snapshots are append-only through ORM services. Source/document SHA-256 and chained events provide local integrity checks.
- Evidence downloads are attachments with nosniff; file names cannot become archive paths.
- Financial exports escape CSV formulas and explicitly encode Excel cells as text. Uploaded content is never executed.
- AI receives scoped facts and metadata with no execution tools. Output schema and evidence references are validated.
- Local launch and Docker expose API/dashboard only on loopback.

## Before sensitive data or public deployment

Deploy TLS and an appropriate identity provider with SSO/MFA and recovery. Add session lifecycle administration, password policies and distributed registration/login throttling. Disable open organization registration when onboarding is operator-managed. Enforce PostgreSQL RLS read policies, narrowly privileged service roles and a credential vault. Implement encrypted object storage, malware scanning, access logging, retention and residency controls. Validate disaster recovery and perform independent penetration testing.

SQLite supports local evaluation, not concurrent enterprise processing. PostgreSQL constraints/configuration have not been load-tested in a live deployment. ORM append-only rules are not database-administrator-proof. Hash-chain assurance requires independently anchored hashes. Model output may still be unsupported even when cited source IDs are valid; human accounting review is mandatory.

No certification, legal compliance, availability guarantee or security audit completion is claimed.

Release 0.6 adds native ML-KEM-768 encrypted JSON/evidence storage, ML-DSA-65 signed audit packages, key custody outside OneDrive, own-session revocation, host filtering, request limits, security headers and fail-closed production prerequisites. See PQC-SECURITY.md for exact boundaries. Encryption keys are required by default; no blanket quantum-proof guarantee is made.
