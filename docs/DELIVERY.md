# Delivery — 11 October 2026

This ZIP contains the complete current project source, tests, migrations, deployment templates, documentation, frontend production build and dependency manifests. It is a development release, not a claim that every enterprise requirement is implemented. FOUNDATION-STATUS.md and REQUIREMENTS-COVERAGE.md list unfinished work.

Extract to a local folder outside OneDrive, for example C:\Finance\AI-Finance-OS. Install Python and Node.js compatible with backend/requirements.lock.txt and frontend/package-lock.json. In backend, create .venv, install requirements.txt, then run .venv\Scripts\python.exe -m app.security_admin init to create a new private encryption keyring. Never replace an existing keyring used by encrypted customer data. Copy .env.example to .env only when needed and configure secrets locally. From the project root run Start-Finance.ps1 -WebPort 5174. Subsequent starts can use -SkipInstall. Stop-Finance.ps1 stops recorded local services.

No private keys, .env secrets, local databases, encrypted backups, running processes or installed dependency folders are included. A fresh extraction starts with a new database. Existing financial data requires a separately protected backup and its original keyring; do not put those into this distribution ZIP.

The package manifest records SHA-256 hashes for every included file. Backend verification: 65 tests passed. Frontend production build passed. Live OpenAI, production deployment, SSO/MFA, managed key rotation and independent certification remain incomplete or unverified as documented.

Passwordless local owner update: after dependency installation and key initialization, run Open-Owner.ps1 -SkipInstall. Open http://127.0.0.1:5174 and click Open local owner workspace. Configured owner is bhuvanjakkula@gmail.com. The email is a local identifier, not verified email identity. Anyone able to access this computer's loopback service can open the configured owner account. Never expose this mode publicly; production refuses it. Local features require no subscription. OpenAI calls remain optional and separately billed. API now uses port 8001 to avoid another local app.
