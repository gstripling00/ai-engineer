# Chapter 9 — Routing and Coordination

Notebook: `Aegis_Chapter9_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `routing/router.py` | `ROUTE_DESCRIPTIONS`, `semantic_route`, `route_scores`, `route_with_confidence`, `severity_route`, `route_with_fallback`, `build_escalation` |
| `routing/mcp_discovery.py` | A real MCP capability server, `discover_routes`, `route_via_discovery` |
| `demo.py` | Smoke test across every section; CI runs it |

Run from the repo root: `python labs/chapter-09-routing-and-coordination/demo.py`
