# Security release 0.6 — precise protection boundaries

The local instance has ML-KEM-768 encrypted financial JSON payloads and evidence, plus ML-DSA-65 signatures on audit packages. This is an application storage/signature implementation using the maintained cryptography library's native primitives. It is not a claim that the entire system is quantum-proof, that the crypto module is FIPS validated, or that customer deployment is certified secure.

## Implemented and activated locally

Every mapped platform JSON column and evidence binary content is encrypted on writes and decrypted after database retrieval. The storage format encapsulates an ML-KEM-768 secret, derives an AES-256-GCM key with HKDF-SHA256 and authenticates a versioned suite/key/nonce header plus a table-column context. Ciphertext tampering and wrong context are rejected. Fresh encapsulation and nonce are generated for each value. Original source/document hash semantics remain unchanged after decrypting, preserving reconciliation and audit-chain compatibility. The envelope format combines standardized primitives, but is application-specific and needs independent cryptographic review. It has no forward secrecy against later compromise of the stored KEM private key.

The existing SQLite JSON rows were migrated offline after stopping services, with an encrypted consistent backup first. Indexed scalar columns (names, email, dates, references, roles, amounts and other relational metadata) remain plaintext. Table-column binding does not prevent an administrator swapping ciphertext between rows of the same column. Tenant authorization and source/audit hashes are separate controls; deployment needs full encrypted volumes/database storage and narrowly privileged database roles. SQLite is local evaluation storage.

Audit ZIPs contain pqc-receipt.json: ML-DSA-65 signs the organization/entity/time and SHA-512 digests of each other archive member. Verification must pin a trusted public key obtained out of band; trusting only a key embedded in a receipt allows substitution. This authenticates a package under its configured signing key, not an independent external timestamp, WORM record or certification of accounting facts. Downloads are plaintext to the authorized recipient and must be stored securely.

Security headers prevent caching and framing and restrict browser permissions. Host allowlisting and an 8 MB body limit apply. Sessions can be listed/revoked by their owner. Password verification fails safely on malformed stored hashes. Production startup rejects missing managed-key path, open registration, automatic schema creation, absent host allowlist and disabling required HTTPS. Production API requests require HTTPS and interactive API docs are disabled. Session/RBAC and independent approval controls remain in effect.

## Key custody and migration

Local default key path on Windows: %LOCALAPPDATA%/AIFinanceOS/security/keyring.json, outside the OneDrive project. Windows ACLs restrict the directory and key to the current account. This is a local development key store, not an HSM; a compromised account/process can read the keys. Keys are never returned by an API or included in project ZIPs. Securely back up keys separately: losing the key loses access to encrypted records. No automatic key rotation or multi-key recovery is implemented; do not overwrite the key file. Existing encrypted rows fail if the key is missing or wrong.

Operator commands from backend:

```powershell
.\.venv\Scripts\python.exe -m app.security_admin init
.\.venv\Scripts\python.exe -m app.security_admin public
.\.venv\Scripts\python.exe -m app.security_admin migrate
.\.venv\Scripts\python.exe -m app.security_admin verify --archive audit-evidence.zip --trusted-key C:\trusted\signing-public-key.txt
```

Run init only on a new deployment. Stop API/worker for migrate. The migration encrypts a consistent SQLite backup, rewrites payload/blob columns and vacuums the working file. It cannot prove erasure of past filesystem snapshots, OneDrive history, SSD remnants or old backups; those need operator retention/removal policy. PostgreSQL migration is deliberately blocked pending a reviewed backup/migration procedure. In production set FINANCE_KEYRING_FILE to a managed secret mount; replace local key loading with an audited HSM/KMS custody integration before onboarding customers. Startup now requires encryption keys by default. An extracted ZIP must initialize its own private keyring offline before starting. Explicit FINANCE_REQUIRE_ENCRYPTION=false permits unencrypted synthetic-only development; production always requires keys. Legacy plaintext reads remain available during development migration only. `/security/status` is owner-only and exposes this configuration state explicitly.

## Transport and production prerequisites

deploy/nginx-pqc.conf is an undeployed strict hybrid TLS template requiring nginx linked to OpenSSL 3.5+ and clients supporting X25519MLKEM768 or SecP256r1MLKEM768. TLS 1.3, body/time limits, disabled tickets and static-site headers are configured. It requires a real hostname/certificate, private API network and actual negotiated-group tests. Traditional certificate signatures remain classical; hybrid key exchange alone is not fully PQ authentication. ERP/model provider connections depend on their negotiated TLS support and are not guaranteed PQ protected.

Build frontend with VITE_API_URL=/api for same-origin hosting. Configure FINANCE_ENV=production, FINANCE_KEYRING_FILE, FINANCE_ALLOWED_HOSTS, ALLOW_REGISTRATION=false and FINANCE_AUTO_CREATE=false. Use HTTPS at the gateway and trust forwarded headers only from that gateway; never use wildcard trusted proxies or expose the plain HTTP backend publicly. Add managed database/disk encryption, SSO/MFA, vault/key rotation, RLS, external immutable integrity anchors, malware scanning, monitoring/abuse controls, backup recovery exercises and independent penetration/crypto reviews. The local demo remains loopback HTTP; it is not a customer-facing deployment.

## Standards and implementation sources

- [NIST FIPS 203 — ML-KEM](https://csrc.nist.gov/pubs/fips/203/final)
- [NIST finalized PQC standards](https://www.nist.gov/news-events/news/2024/08/nist-releases-first-3-finalized-post-quantum-encryption-standards)
- [cryptography ML-KEM interface](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/mlkem/)
- [cryptography ML-DSA interface](https://cryptography.io/en/stable/hazmat/primitives/asymmetric/mldsa/)
- [OpenSSL 3.5 hybrid TLS groups](https://docs.openssl.org/3.5/man3/SSL_CONF_cmd/)


Local preview serves built assets with same-origin /api forwarding and bounded request concurrency; it does not expose the Vite source/HMR development interface. Vite preview is a local evaluation server, not a replacement for the production TLS gateway.

## Signed-package verification hardening — 11 October
Receipt verification now rejects unexpected unsigned fields and invalid metadata. Offline ZIP verification rejects unsafe archive paths, caps receipt size at 1 MB, requires valid SHA-512 digest strings and streams member hashes in 64 KiB chunks with a 200 MB expanded-content bound. Trusted public-key pinning remains mandatory. No keys or ciphertext formats were replaced. These parser/resource controls strengthen the existing ML-DSA package verification; they do not add PQ transport, managed key rotation or security certification.
