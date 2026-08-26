# Chapter 13 — The Capstone: Aegis, Assembled

Notebook: `Aegis_Chapter13_Lab.ipynb` — it adds this folder to `sys.path` (and Chapter 6's,
for the runbook corpus) and imports the modules below.

| File | What it is |
|---|---|
| `common/soc.py`, `common/model.py` | The SOC world and the `AEGIS_MODEL` seam (same as Chapter 8) |
| `capstone/aegis/system.py` | `AegisV12` — every chapter's component in one pipeline; returns a `Run` (findings dict + tracer views). The same file ships in Chapter 10. |
| `capstone/aegis/soc_formats.py` | Wazuh / Sigma / MISP fixtures and adapters: `from_wazuh`, `parse_sigma`, `routing_corpus_from_sigma`, `from_misp`, `reputation_from_misp` |
| `interface/render.py` | `interface_contract`, `render_ticket_comment` |
| `demo.py` | Smoke test across every section; CI runs it |

Run from the repo root: `python labs/chapter-13-assembling-aegis/demo.py`
