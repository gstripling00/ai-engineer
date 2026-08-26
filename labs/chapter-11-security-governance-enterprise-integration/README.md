# Optional Lab 11B — Security Across the Handoff

Notebook: `Aegis_Chapter11B_Lab.ipynb`. Imports Chapter 8's team and Chapter 11's scanner
from their own folders; adds the controls below.

| File | What it is |
|---|---|
| `handoff/security.py` | `Field` (provenance + taint), `field_from_untrusted`, `derive`, `taint_check`, `sign` / `verify`, `receive`, `new_keys` |
| `demo.py` | Smoke test; CI runs it |

Run from the repo root: `python labs/chapter-11b-security-across-the-handoff/demo.py`
