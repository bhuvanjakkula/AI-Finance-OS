# Reverse liquidity stress test — 11 October 2026

Cash Intelligence can now determine the maximum uniform reduction in a saved forecast's weekly collections while preserving a user-selected cash reserve. The engine performs monotone binary search over 0–100% losses at 0.01 percentage-point resolution, conservatively rounding retained weekly inflows down to cents. Outflows and timing stay fixed. Opening cash and each weekly closing balance must meet the reserve.

The output includes the loss limit, the first breach after a further 0.01 percentage-point reduction, weekly retained receipts and reserve headroom, baseline funding needs and funding needs with zero collections. Baselines already below reserve return no feasible loss limit. Cases surviving zero collections are labeled explicitly. Inputs and results are encrypted saved runs linked to the original forecast, with an audit event.

POST /cash/liquidity-limits accepts forecast_id and reserve. Writers may create results; auditors can inspect saved runs through /runs. Organization scoping and forecast-type validation apply. No database migration or external provider is required.

This is a deterministic scenario boundary, not a probability of loss, market-risk model or credit decision. Timing shocks, intraweek liquidity, financing costs and source completeness are not modeled. Reduced inflows apply on top of the saved scenario's assumptions.

Verification: 53 tests pass; production build passes. Golden tests prove a 30.00% boundary, breach at the next step, opening deficits, zero-collection survival, funding arithmetic, saved lineage, invalid inputs and access restrictions. Browser saved a synthetic result: 51.20% maximum loss at a USD 100,000 reserve; next-step breach at 21 October 2026.
