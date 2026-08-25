"""
Structured output, validated before execution.

A model emits a tool call as text. That text can be wrong in three ways that
matter, and all three arrive looking identical: a tool that does not exist,
arguments that do not match the schema, or a string that is not JSON at all.

validate_tool_call() turns each of those into DATA rather than an exception.
guarded_dispatch() executes only calls that passed. The rule is fail closed: a
rejected call is something you can log, count, and alert on. A crash is none
of those things. Chapter 11 reuses this seam to reject *unauthorized* calls.

Standard library only — the schema subset the labs use (object, required,
typed properties) does not need a jsonschema dependency.
"""
import json

_JSON_TYPES = {
    "string": str, "integer": int, "number": (int, float), "boolean": bool,
    "object": dict, "array": list, "null": type(None),
}


def _schema_for(name: str, schemas: list) -> dict | None:
    for schema in schemas:
        if schema.get("function", {}).get("name") == name:
            return schema["function"].get("parameters", {"type": "object"})
    return None


def _check_arguments(arguments: dict, params: dict) -> str | None:
    """Return a reason string if `arguments` violate `params`, else None."""
    if not isinstance(arguments, dict):
        return "arguments must be an object"
    props = params.get("properties", {})
    for key in params.get("required", []):
        if key not in arguments:
            return f"missing required '{key}'"
    for key, value in arguments.items():
        if key not in props:
            return f"unexpected argument '{key}'"
        expected = _JSON_TYPES.get(props[key].get("type"))
        if expected is not None and not isinstance(value, expected):
            return f"'{key}' must be {props[key]['type']}"
        if expected is int and isinstance(value, bool):
            return f"'{key}' must be integer"
    return None


def validate_tool_call(raw: str, registry: dict, schemas: list) -> dict:
    """
    Parse and check a raw tool call. Never raises.

    Returns {"ok": bool, "reason": str, "name": str | None, "arguments": dict | None}
    reason is one of: accepted, malformed_json, unknown_tool, bad_arguments.
    """
    try:
        call = json.loads(raw)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "malformed_json", "name": None, "arguments": None}

    if not isinstance(call, dict) or "name" not in call:
        return {"ok": False, "reason": "malformed_json", "name": None, "arguments": None}

    name = call["name"]
    arguments = call.get("arguments", {})
    if isinstance(arguments, str):                      # some models stringify arguments
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return {"ok": False, "reason": "malformed_json", "name": name, "arguments": None}

    params = _schema_for(name, schemas)
    if name not in registry or params is None:
        return {"ok": False, "reason": "unknown_tool", "name": name, "arguments": arguments}

    problem = _check_arguments(arguments, params)
    if problem:
        return {"ok": False, "reason": "bad_arguments", "name": name,
                "arguments": arguments, "detail": problem}

    return {"ok": True, "reason": "accepted", "name": name, "arguments": arguments}


def guarded_dispatch(raw: str, registry: dict, schemas: list) -> dict:
    """
    Validate, then execute only if validation passed.

    Returns {"ok": bool, "reason": str, "result": str | None}. On rejection,
    result is None and nothing was executed.
    """
    verdict = validate_tool_call(raw, registry, schemas)
    if not verdict["ok"]:
        return {"ok": False, "reason": verdict["reason"], "result": None,
                "detail": verdict.get("detail")}
    result = registry[verdict["name"]](**verdict["arguments"])
    return {"ok": True, "reason": "accepted", "result": result}


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from function_calling.tools_fc import REGISTRY, SCHEMAS

    cases = [
        json.dumps({"name": "ip_reputation", "arguments": {"ip": "203.0.113.42"}}),
        json.dumps({"name": "delete_all_logs", "arguments": {}}),
        json.dumps({"name": "ip_reputation", "arguments": {"wrong": 1}}),
        "{not json at all",
    ]
    for raw in cases:
        out = guarded_dispatch(raw, REGISTRY, SCHEMAS)
        print(f'ok={str(out["ok"]):5} reason={out["reason"]:15} '
              f'{(out["result"] or "-")[:40]}')
