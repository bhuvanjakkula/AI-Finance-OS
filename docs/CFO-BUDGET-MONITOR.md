# CFO budget exception monitor — 11 October 2026

Financial Reporting now provides a materiality-based review for any organization's mapped revenue/expense accounts. The selected entity and period determine actuals from active journals and latest sequential budget versions. Users choose an absolute currency threshold.

Revenue shortfalls and expense overruns reduce budgeted earnings. Material adverse variances are flagged at or above the threshold; missing budgets with material nonzero actuals are flagged separately. Zero budgets do not produce percentage variances. The earnings bridge includes budgeted accounts only, so it is not a complete forecast/profit estimate when budgets are missing. Rows prioritize flagged accounts and absolute earnings impact.

POST /reports/budget-exceptions accepts entity_id, period and materiality. Writers create encrypted review snapshots and audit events; auditors can inspect saved runs through /runs. Snapshots retain account values and budget versions. No database migration or industry-specific model is required. Source completeness, budget quality and industry accounting policies remain customer validation work. This tool does not approve spending, adjust journals or provide accounting certification.

Verification: 62 backend tests pass; production build passes. Tests cover adverse revenue signs, inclusive materiality boundaries, missing budgets, snapshot creation, authorization and invalid inputs. Full suite also verifies existing intercompany workflows. Browser correctly flagged both unbudgeted accounts in the synthetic workspace and saved the review.
