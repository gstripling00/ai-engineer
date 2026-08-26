"""
§11.6 MCP hardening: a tool registry is a supply chain.

A server you do not own controls each tool's DESCRIPTION - prose delivered
verbatim into your model's context. Discovery happens on every connection, so
a server can be benign on Monday and hostile on Tuesday (a rug pull).

  screen_tool_definition   the description is untrusted text; scan it like a log line
  pin_tools                fingerprint what you approved (name + description + schema)
  detect_rug_pull          compare today's advertisement to the pinned fingerprints
  MCPGuard                 per-server scopes: a server may only offer tools you expect
"""
import hashlib
import json

from .hardening import scan_for_injection


def screen_tool_definition(tool: dict) -> dict:
    phrases = scan_for_injection(tool.get("description", "") + " " + json.dumps(tool.get("inputSchema", {})))
    return {"name": tool.get("name"), "safe": not phrases, "injection_phrases": phrases}


def fingerprint(tool: dict) -> str:
    canonical = json.dumps({"name": tool.get("name"), "description": tool.get("description", ""),
                            "inputSchema": tool.get("inputSchema", {})}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def pin_tools(tools: list) -> dict:
    """{name: fingerprint} for the definitions you reviewed and approved."""
    return {t["name"]: fingerprint(t) for t in tools}


def detect_rug_pull(pinned: dict, current: list) -> dict:
    """Same name, different prose or schema -> 'changed'. Anything new -> 'added'."""
    now = {t["name"]: fingerprint(t) for t in current}
    changed = sorted(n for n in pinned if n in now and now[n] != pinned[n])
    added = sorted(n for n in now if n not in pinned)
    removed = sorted(n for n in pinned if n not in now)
    return {"clean": not (changed or added or removed), "changed": changed, "added": added, "removed": removed}


class MCPGuard:
    """Approve a server's advertised tools against the scope you granted it and the
    injection screen. Unexpected or poisoned tools are rejected with a reason."""

    def __init__(self, server_scopes: dict):
        self.server_scopes = {s: set(tools) for s, tools in server_scopes.items()}
        self.pinned: dict = {}

    def approve(self, server: str, tools: list) -> dict:
        scope = self.server_scopes.get(server, set())
        approved, rejected = [], []
        for tool in tools:
            name = tool.get("name")
            if name not in scope:
                rejected.append((name, "outside the scope granted to this server"))
                continue
            screen = screen_tool_definition(tool)
            if not screen["safe"]:
                rejected.append((name, f"injection phrases in description: {screen['injection_phrases']}"))
                continue
            approved.append(name)
        self.pinned[server] = pin_tools([t for t in tools if t.get("name") in approved])
        return {"server": server, "approved": approved, "rejected": rejected}

    def recheck(self, server: str, tools: list) -> dict:
        return detect_rug_pull(self.pinned.get(server, {}), tools)
