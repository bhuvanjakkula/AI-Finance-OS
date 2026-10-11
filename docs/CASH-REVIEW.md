# Cash forecast reliability review

Open Cash Intelligence, select a saved cash scenario, enter a review date and a cash error tolerance, then choose Compare with bank actuals.

The comparison uses frozen scenario outputs and currently imported bank transactions for the same organization, entity and currency. Only complete forecast weeks ending on or before the review date are included. Future review dates are rejected. Error is imported actual minus forecast; outflow error is actual positive spending minus projected spending. Mean absolute net error uses only weeks containing bank records. All amounts use Decimal arithmetic and round to cents.

Weeks with no bank records are flagged separately. Imported bank coverage is not certified, including weeks containing some records. Source record IDs support manual review. Internal transfers are included if imported; this feature does not consolidate bank accounts, certify ending balances or estimate statistical confidence. A forecast saved on or after its start date is labeled retrospective to avoid presenting it as out-of-sample validation. Review output is computed live and does not alter the saved forecast.

API: GET /cash/forecasts/{run_id}/review?as_of=YYYY-MM-DD&tolerance=100.00. Authenticated read access includes auditors; foreign-organization snapshots return 404. No database migration or external service is needed.

Verification on 11 October 2026: 47 backend tests passed; Vite production build passed. Golden tests cover cents, week boundaries, missing observations, threshold alerts, auditors, anonymous requests, cross-organization access and invalid/future inputs. Browser verified the existing synthetic scenario, retrospective warning and exclusion of unfinished weeks. Live banking completeness remains unverified.
