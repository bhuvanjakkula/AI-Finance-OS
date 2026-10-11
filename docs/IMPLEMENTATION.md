# Implementation summary

Release 0.3 replaces the exposed starter demo API with authenticated canonical platform services. Original demonstration source is retained in legacy_main.py for regression coverage; it is not included as a router in the running platform.

Core modules: auth.py, contracts.py, platform_models.py, finance_engine.py, erp.py, agents.py, exports.py, worker.py and main.py. Frontend provides organization setup, all eight module screens, financial forms, review actions, source inspection and download flows.

See ARCHITECTURE.md for correctness boundaries, API.md for service contracts, CONNECTORS.md for deployment credentials and REQUIREMENTS-COVERAGE.md for blueprint coverage. Verification results are reported separately in VERIFICATION.md.
