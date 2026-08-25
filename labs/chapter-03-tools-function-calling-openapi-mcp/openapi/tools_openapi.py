"""
Mechanism 2 — generating tool schemas from an OpenAPI spec.

Most companies already have an API specification for their internal services.
If you have one, you do not write tool schemas at all: openapi_to_schemas()
turns every operation into a function-call schema mechanically. Add an
endpoint to the spec, re-run the converter, and the agent gains a tool.

    python labs/chapter-03-tools-function-calling-openapi-mcp/openapi/tools_openapi.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soc_tools import TOOLS  # noqa: E402

SOC_OPENAPI = {
    "openapi": "3.0.0",
    "info": {"title": "SOC API", "version": "1.0"},
    "paths": {
        "/logs/search": {
            "post": {
                "operationId": "search_logs",
                "summary": "Search SIEM logs by event type or username.",
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"},
                                   "window": {"type": "string"}},
                    "required": ["query"]}}}},
            }
        },
        "/intel/reputation": {
            "post": {
                "operationId": "ip_reputation",
                "summary": "Look up threat-intel reputation for an IP address.",
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {"ip": {"type": "string"}},
                    "required": ["ip"]}}}},
            }
        },
    },
}


def openapi_to_schemas(spec: dict) -> list:
    """Mechanically convert every operation in an OpenAPI spec into a tool schema."""
    schemas = []
    for _path, methods in spec["paths"].items():
        for _method, op in methods.items():
            body = (op.get("requestBody", {}).get("content", {})
                      .get("application/json", {})
                      .get("schema", {"type": "object", "properties": {}}))
            schemas.append({"type": "function", "function": {
                "name": op["operationId"],
                "description": op.get("summary", ""),
                "parameters": body}})
    return schemas


SCHEMAS = openapi_to_schemas(SOC_OPENAPI)                  # generated, not typed
REGISTRY = {s["function"]["name"]: TOOLS[s["function"]["name"]]
            for s in SCHEMAS if s["function"]["name"] in TOOLS}


def dispatch(name: str, args: dict) -> str:
    fn = REGISTRY.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    return fn(**args)


if __name__ == "__main__":
    print("openapi — schemas generated from the spec")
    for schema in SCHEMAS:
        print(f'  {schema["function"]["name"]:15} {schema["function"]["description"]}')
    result = json.loads(dispatch("ip_reputation", {"ip": "203.0.113.42"}))
    print(f'\nip_reputation -> {result["verdict"]} (score {result["score"]})')
    print("hand-written JSON schema: 0 characters")
