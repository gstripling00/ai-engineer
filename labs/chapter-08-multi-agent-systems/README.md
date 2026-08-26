# Chapter 8 — Multi-Agent Systems

Notebook: `Aegis_Chapter8_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `common/soc.py` | The SOC world: `SEED_ALERT`, logs, four tools, `TICKETS` / `reset_tickets` |
| `common/model.py` | `get_model()` — the `AEGIS_MODEL` seam (mock, or OpenAI over stdlib urllib) |
| `common/a2a.py` | `A2AMessage` envelope with `trace_id`, `new_investigation` |
| `common/workers.py` | `TRIAGE_TOOLS` / `INVEST_TOOLS` / `REPORT_TOOLS`, `authorized_call`, the three workers |
| `common/coordination.py` | `Delegation` + `MAX_HANDOFFS` (§8.3.3), `fan_out` + `merge` (§8.4) |
| `demo.py` | Smoke test across every section; CI runs it |

Run from the repo root: `python labs/chapter-08-multi-agent-systems/demo.py`
