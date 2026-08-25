# Chapter 5 — Memory

Notebook: `Aegis_Chapter5_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `memory/context_budget.py` | Working memory under a token budget: `count_tokens`, `truncate`, `sliding_window`, `summarize_middle` |
| `memory/memory_store.py` | `EpisodicMemory` (similarity + threshold), `SEMANTIC_FACTS` / `is_known_bad_sender`, `ProceduralMemory`, `assess_with_memory` |
| `demo.py` | Smoke test covering every section; CI runs it |

Run from the repo root: `python labs/chapter-05-memory/demo.py`
