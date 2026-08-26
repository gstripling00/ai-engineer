# Chapter 12 — Deployment

Notebook: `Aegis_Chapter12_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `deployment/deploy.py` | `eval_gate`, `canary_decision` (→ `CanaryResult`), `check_slos` with `SLOS` |
| `deployment/release_policy.py` | Dated `PRICES` + `PRICES_VERIFIED`, `STAGE_TOKENS`, `stage_model` / `stage_cost` / `incident_cost`, `retirement_warnings`, `cost_gate`, `release` |
| `demo.py` | Smoke test across every section; CI runs it |

Run from the repo root: `python labs/chapter-12-deployment/demo.py`

The price table and `RETIREMENTS` are dated facts. Re-verify them (and Appendix G) before print.
