#!/usr/bin/env python3
"""Build the Chapter 3 canonical lab notebook."""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from lab_builder import md, code, build      # noqa: E402

OUT = os.path.join(REPO, "ch03", "Aegis_Chapter3_Lab.ipynb")

INTRO = [
    md("# Chapter 3 — Giving Agents Tools",
       "",
       "In Chapter 1 a tool was a function in a dictionary. That works, and it does not scale:",
       "every tool needs a hand-written schema, nothing is shared between agents, and a tool",
       "added by one team is invisible to every other.",
       "",
       "There are three mechanisms, and they differ in who owns the schema, when the schema is",
       "known, and how much reuse you get — not in what the agent can do.",
       "",
       "**Covered in this lab:** §3.2 function calling · §3.3 structured output *and",
       "validation before execution* · §3.5.2 generating tools from OpenAPI · §3.5.3 MCP",
       "runtime discovery (the real SDK) · §3.5.4 choosing a strategy."),
]

BODY = [
    md("## §3.2 — Function calling",
       "",
       "You hand-write the schema: name, description, and a JSON Schema for the arguments.",
       "The model reads it to decide what to call and with what.",
       "",
       "Count the characters. Now imagine forty tools. That cost is the motivation for the",
       "next two mechanisms."),
    code('''import json, sys
sys.path.insert(0, "ch03")

from function_calling.tools_fc import (IP_REPUTATION_SCHEMA, SCHEMAS as FC_SCHEMAS,
                                       REGISTRY as FC_REGISTRY, dispatch as fc_dispatch)

print("function calling — hand-written schema:")
print(f'  {len(json.dumps(IP_REPUTATION_SCHEMA))} chars of JSON, written by a human')
print(f'  tools exposed: {[s["function"]["name"] for s in FC_SCHEMAS]}')
print()

verdict = json.loads(fc_dispatch("ip_reputation", {"ip": "203.0.113.42"}))
print("  result:", verdict["verdict"], f'(score {verdict["score"]})')'''),

    md("## §3.3 — Structured output, and validating it before execution",
       "",
       "A model emits a tool call as *text*. Text can be wrong in three ways that matter, and",
       "all three arrive looking identical: a tool that does not exist, arguments that do not",
       "match, or output that is not valid JSON at all.",
       "",
       "Validation turns each of those into **data** instead of an exception. The rule is",
       "**fail closed**: a rejected call is something you can log, count, and alert on. A crash",
       "is none of those things.",
       "",
       "This is also the seam Chapter 11 builds on — the function that rejects a malformed",
       "call is the natural place to reject an *unauthorized* one."),
    code('''from validation import validate_tool_call, guarded_dispatch

CASES = [
    ("valid call    ", json.dumps({"name": "ip_reputation",
                                   "arguments": {"ip": "203.0.113.42"}})),
    ("unknown tool  ", json.dumps({"name": "delete_all_logs", "arguments": {}})),
    ("bad arguments ", json.dumps({"name": "ip_reputation", "arguments": {"wrong": 1}})),
    ("malformed json", "{not json at all"),
]

for label, raw in CASES:
    outcome = guarded_dispatch(raw, FC_REGISTRY, FC_SCHEMAS)
    result = (outcome["result"][:34] + "...") if outcome["result"] else "-"
    print(f'{label}  ok={str(outcome["ok"]):5} reason={str(outcome["reason"]):15} {result}')

print()
print("Nothing raised. Every rejection is a value the agent can act on.")'''),

    md("## §3.5.2 — Generating the tool registry from an OpenAPI spec",
       "",
       "Most companies already have an API specification for their internal services. If you",
       "have one, you do not write tool schemas at all — you generate them.",
       "",
       "The cell below adds an endpoint to the spec and re-runs the converter. You write no",
       "schema; the agent gains a tool."),
    code('''import copy
from openapi.tools_openapi import SOC_OPENAPI, openapi_to_schemas

before = openapi_to_schemas(SOC_OPENAPI)
print(f'schemas before: {len(before)}  {[s["function"]["name"] for s in before]}')

extended = copy.deepcopy(SOC_OPENAPI)
extended["paths"]["/identity/user"] = {
    "post": {"operationId": "user_context",
             "summary": "Fetch an account's role, department, and privilege level.",
             "requestBody": {"content": {"application/json": {"schema": {
                 "type": "object",
                 "properties": {"user": {"type": "string"}},
                 "required": ["user"]}}}}}
}

after = openapi_to_schemas(extended)
print(f'schemas after:  {len(after)}  {[s["function"]["name"] for s in after]}')
print()
print("hand-written JSON schema: 0 characters")'''),

    md("## §3.5.3 — MCP: runtime discovery",
       "",
       "The Model Context Protocol inverts the relationship. Instead of the client knowing",
       "what tools exist, a **server advertises** them and any client discovers them at",
       "runtime.",
       "",
       "That is a genuinely different property. With function calling and OpenAPI the tool",
       "list is compiled into the client. With MCP, a tool added to the server this morning is",
       "available to every agent this afternoon — no client change, no redeploy.",
       "",
       "This uses the real `mcp` SDK over its in-memory transport, so it runs offline."),
    code('''import asyncio
from mcp.shared.memory import create_connected_server_and_client_session
from mcp_track.tools_mcp import build_soc_server


async def discover_and_call():
    server = build_soc_server()
    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        listed = await client.list_tools()                      # DISCOVERY
        names = [t.name for t in listed.tools]
        called = await client.call_tool("ip_reputation", {"ip": "203.0.113.42"})
        return names, json.loads(called.content[0].text)


names, result = asyncio.run(discover_and_call())

print("tools discovered at runtime:", names)
print("nothing about these was hard-coded on the client")
print()
print("called ip_reputation ->", result["verdict"])'''),

    md("## §3.5.4 — Choosing a strategy",
       "",
       "Three mechanisms, one verdict. Check the thing that actually matters, then choose on",
       "the things that differ."),
    code('''fc_verdict = json.loads(fc_dispatch("ip_reputation", {"ip": "203.0.113.42"}))["verdict"]
oa_verdict = json.loads(
    __import__("openapi.tools_openapi", fromlist=["dispatch"]).dispatch(
        "ip_reputation", {"ip": "203.0.113.42"}))["verdict"]
mcp_verdict = result["verdict"]

print("verdict by mechanism:")
print("  function calling:", fc_verdict)
print("  openapi:         ", oa_verdict)
print("  mcp:             ", mcp_verdict)
assert fc_verdict == oa_verdict == mcp_verdict
print("  -> identical. the mechanism does not change the answer.")
print()

TRADEOFFS = [
    ("Function calling", "high (hand-write each)", "no", "no"),
    ("OpenAPI", "low (one spec -> N tools)", "via shared spec", "no"),
    ("MCP", "low (server declares)", "yes (any client)", "yes"),
]

print(f'  {"mechanism":18} {"effort per tool":26} {"cross-agent reuse":18} runtime discovery')
for mechanism, effort, reuse, discovery in TRADEOFFS:
    print(f'  {mechanism:18} {effort:26} {reuse:18} {discovery}')
print()
print("Rule of thumb: one tool in one process -> function calling.")
print("An API you already have a spec for -> OpenAPI.")
print("Tools shared across agents or teams -> MCP earns its complexity.")'''),

    md("### One warning before you ship any of this",
       "",
       "Look at what a tool definition actually sends the model: a name, and a **description",
       "in prose**. That description goes into the model's context — and in the MCP case it",
       "comes from a server you may not own.",
       "",
       "The callable can be perfectly correct while the prose is the attack. That is tool",
       "poisoning, and Chapter 11 builds the defense: screen the description, fingerprint what",
       "you approved, and detect the rug pull when a server rewrites it later."),
]

CLOSING = [
    md("---",
       "",
       "## What you built",
       "",
       "The same tool wired three ways to the same verdict, a validator that fails closed, and",
       "runtime discovery over the real MCP protocol.",
       "",
       "- **The mechanism does not change the answer.** It changes schema effort, reuse, and",
       "  whether tools can be discovered rather than compiled in.",
       "- **Validate before you execute.** A rejected call is data; a crash is not.",
       "- **A tool description is an instruction channel.** A registry you do not govern is a",
       "  supply chain you do not control.",
       "",
       "**Next:** Chapter 4 gives Aegis a conversation — interviewing an employee about a",
       "suspicious email and producing a structured incident record."),
]


def main():
    nb = build(3, "Giving Agents Tools", INTRO, BODY, CLOSING)
    with open(OUT, "w") as f:
        json.dump(nb, f, indent=1)
    print("wrote", os.path.relpath(OUT, REPO),
          f"({len(nb['cells'])} cells, {sum(1 for c in nb['cells'] if c['cell_type']=='code')} code)")


if __name__ == "__main__":
    main()
