# Treasury stress lab

Cash Intelligence now compares five deterministic stress cases using a saved 13-week cash forecast: baseline, delayed collections, reduced collections, payment shock and combined stress. Users choose a minimum reserve, additional collection delay in whole weeks and inflow/outflow multipliers. Factors apply on top of the saved forecast assumptions.

Each case shows opening/weekly minimum cash, final cash, first weekly reserve breach, additional starting cash required to maintain the reserve and delayed receipts pushed beyond the forecast horizon. Weekly paths and explicit assumptions support controller review. Inputs and outputs are saved as encrypted AnalysisRun payloads with source forecast ID and an audit event.

POST /cash/stress accepts forecast_id, reserve, collection_delay_weeks, inflow_factor and outflow_factor. Writers can create runs; auditors can read saved output through /runs. Organization scope is enforced. No schema migration or external data provider is needed.

These are cash-flow scenarios, not probabilities, investment recommendations or VaR estimates. Intraweek liquidity, financing costs, market-price risk, rates, FX and instrument valuation are not modeled. Bank/source completeness remains external validation. Delayed receipts beyond week 13 remain separately disclosed rather than being counted as lost collections.

Verification — 11 October 2026: 48 tests pass; frontend production build passes. Tests verify exact funding calculations, delay placement, horizon truncation, opening reserve breaches, saved lineage, role restrictions, invalid inputs and missing/wrong snapshot types. Browser successfully saved all five cases in the synthetic QA organization. Synthetic combined stress minimum cash was 82,600 versus baseline 112,800 in USD.
