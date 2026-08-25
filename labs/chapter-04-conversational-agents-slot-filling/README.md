# Chapter 4 — Conversational Agents (Slot Filling)

Notebook: `Aegis_Chapter4_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `common/soc.py` | Fixed fixtures: `PHISHING_REPORT`, `VAGUE_REPORT`, `SEED_ALERT` |
| `intake/slot_filling.py` | `REQUIRED_SLOTS`, `clean`, `extract_slots`, `IntakeState`, `apply_extraction`, `to_incident` |
| `intake/intent.py` | `classify_intent`, `split_multi_intent` (multi-intent), `is_interruption`, `handle_turn` |
| `demo.py` | Smoke test covering every section; CI runs it |

Run from the repo root: `python labs/chapter-04-conversational-agents-slot-filling/demo.py`

Focus: intent recognition (including multi-intent), entity extraction, grounded
extraction, slot filling, and interruptions.
