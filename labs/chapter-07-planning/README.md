# Chapter 7 — Planning

Notebook: `Aegis_Chapter7_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `planning/tools.py` | The SOC tools, fixed data, `INCIDENT`, and `TOOL_DESCRIPTIONS` |
| `planning/reasoning.py` | `chain_of_thought` (§7.2) and `select_tool` with a refusal margin (§7.5) |
| `planning/planner.py` | `Step`, `make_plan`, `execute_plan` with recorded replanning (§7.4), `summarize`, `reflect` (§7.6) |
| `scratch/triage_agent.py` | The Chapter 1 ReAct loop, reproduced so §7.3 can contrast it with a plan |
| `demo.py` | Smoke test across every section; CI runs it |

Run from the repo root: `python labs/chapter-07-planning/demo.py`
