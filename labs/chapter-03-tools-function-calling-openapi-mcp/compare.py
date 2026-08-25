"""
The same tool wired three ways, to the same verdict.

    python labs/chapter-03-tools-function-calling-openapi-mcp/compare.py

Exits non-zero if the three mechanisms disagree, so CI can run it as a smoke
test for the whole chapter.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from function_calling.tools_fc import dispatch as fc_dispatch   # noqa: E402
from openapi.tools_openapi import dispatch as oa_dispatch        # noqa: E402
from mcp_track.tools_mcp import discover_and_call                 # noqa: E402

IP = "203.0.113.42"

TRADEOFFS = [
    ("Function calling", "high (hand-write each)",    "no",              "no"),
    ("OpenAPI",          "low (one spec -> N tools)", "via shared spec", "no"),
    ("MCP",              "low (server declares)",     "yes (any client)", "yes"),
]


def main() -> int:
    fc = json.loads(fc_dispatch("ip_reputation", {"ip": IP}))["verdict"]
    oa = json.loads(oa_dispatch("ip_reputation", {"ip": IP}))["verdict"]
    _names, mcp_result = asyncio.run(discover_and_call("ip_reputation", {"ip": IP}))
    mcp = mcp_result["verdict"]

    print("verdict by mechanism:")
    print("  function calling:", fc)
    print("  openapi:         ", oa)
    print("  mcp:             ", mcp)
    if not (fc == oa == mcp):
        print("  -> MISMATCH")
        return 1
    print("  -> identical. the mechanism does not change the answer.\n")

    print(f'  {"mechanism":18} {"effort per tool":26} {"cross-agent reuse":18} runtime discovery')
    for mechanism, effort, reuse, discovery in TRADEOFFS:
        print(f'  {mechanism:18} {effort:26} {reuse:18} {discovery}')
    print()
    print("Rule of thumb: one tool in one process -> function calling.")
    print("An API you already have a spec for -> OpenAPI.")
    print("Tools shared across agents or teams -> MCP earns its complexity.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
