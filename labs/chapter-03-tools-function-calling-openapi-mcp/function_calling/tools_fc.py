"""
Mechanism 1 — function calling.

You hand-write the schema: a name, a description in prose, and a JSON Schema
for the arguments. The model reads the schema to decide what to call and with
what. Count the characters in IP_REPUTATION_SCHEMA, then imagine forty tools.
That cost is the motivation for the other two mechanisms.

    python labs/chapter-03-tools-function-calling-openapi-mcp/function_calling/tools_fc.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soc_tools import ip_reputation, search_logs  # noqa: E402

IP_REPUTATION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ip_reputation",
        "description": "Look up threat-intel reputation for an IP address.",
        "parameters": {
            "type": "object",
            "properties": {"ip": {"type": "string", "description": "IPv4 address"}},
            "required": ["ip"],
        },
    },
}

SEARCH_LOGS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_logs",
        "description": "Search SIEM logs by event type or username.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "event type or username"},
                "window": {"type": "string", "description": "look-back window, e.g. 1h"},
            },
            "required": ["query"],
        },
    },
}

SCHEMAS = [IP_REPUTATION_SCHEMA, SEARCH_LOGS_SCHEMA]      # what the model sees
REGISTRY = {"ip_reputation": ip_reputation,               # what actually runs
            "search_logs": search_logs}


def dispatch(name: str, args: dict) -> str:
    """Route a model-chosen call to the registered callable."""
    fn = REGISTRY.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    return fn(**args)


if __name__ == "__main__":
    print("function calling — hand-written schemas")
    for schema in SCHEMAS:
        fn = schema["function"]
        print(f'  {fn["name"]:15} {len(json.dumps(schema)):4} chars of JSON, typed by a human')
    result = json.loads(dispatch("ip_reputation", {"ip": "203.0.113.42"}))
    print(f'\nip_reputation -> {result["verdict"]} (score {result["score"]})')
