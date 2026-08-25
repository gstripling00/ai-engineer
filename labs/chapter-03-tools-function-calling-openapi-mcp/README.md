# Chapter 3 — Giving Agents Tools

**Chapter title:** Giving Agents Tools: Function Calling, OpenAPI, and MCP

Notebook: `Aegis_Chapter3_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below.

| File | What it is |
|---|---|
| `soc_tools.py` | The tool callables and fixed offline data, shared by all three mechanisms |
| `function_calling/tools_fc.py` | Hand-written schemas: `IP_REPUTATION_SCHEMA`, `SCHEMAS`, `REGISTRY`, `dispatch` |
| `validation.py` | `validate_tool_call`, `guarded_dispatch` — fail-closed validation before execution |
| `openapi/tools_openapi.py` | `SOC_OPENAPI`, `openapi_to_schemas`, generated `SCHEMAS`/`REGISTRY`, `dispatch` |
| `mcp_track/tools_mcp.py` | A real MCP server (`build_soc_server`) and in-memory client discovery |
| `compare.py` | All three mechanisms to the same verdict; CI smoke test |

Each module runs standalone from the repo root, e.g. `python labs/chapter-03-tools-function-calling-openapi-mcp/compare.py`.

Focus: function calling, structured output, tool schemas, API integration, OpenAPI, MCP, validation, security, and sandboxing.
