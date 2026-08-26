# Chapter 11 — Securing the Agent That Secures You

Notebook: `Aegis_Chapter11_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `security/hardening.py` | `scan_for_injection` / `safe_ingest`, `IAM_POLICY` + `authorize` + `AuditLog`, `mask_pii`, `safety_filter` + `guarded_model_call` |
| `security/mcp_hardening.py` | `screen_tool_definition`, `pin_tools`, `detect_rug_pull`, `MCPGuard` |
| `demo.py` | Smoke test across every section; CI runs it |

Run from the repo root: `python labs/chapter-11-security-governance-enterprise-integration/demo.py`
