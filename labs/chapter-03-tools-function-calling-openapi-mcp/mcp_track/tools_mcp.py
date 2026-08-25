"""
Mechanism 3 — MCP runtime discovery, using the real `mcp` SDK.

The Model Context Protocol inverts the relationship: the SERVER advertises its
tools and any client discovers them at runtime. Nothing about the tool list is
compiled into the client. build_soc_server() is a real MCP server; the demo
below connects a real client to it over the SDK's in-memory transport, so it
runs offline and in CI. Swap the transport for stdio or HTTP and nothing else
changes.

(This package is named mcp_track, not mcp, because a local folder called `mcp`
would shadow the installed SDK.)

    python labs/chapter-03-tools-function-calling-openapi-mcp/mcp_track/tools_mcp.py
"""
import asyncio
import json
import os
import sys

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.shared.memory import create_connected_server_and_client_session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soc_tools import TOOLS  # noqa: E402

# What the server ADVERTISES. Add an entry here and every client sees it on its
# next list_tools() — no client change, no redeploy.
ADVERTISED = [
    types.Tool(name="ip_reputation",
               description="Look up threat-intel reputation for an IP address.",
               inputSchema={"type": "object",
                            "properties": {"ip": {"type": "string"}},
                            "required": ["ip"]}),
    types.Tool(name="search_logs",
               description="Search SIEM logs by event type or username.",
               inputSchema={"type": "object",
                            "properties": {"query": {"type": "string"},
                                           "window": {"type": "string"}},
                            "required": ["query"]}),
    types.Tool(name="user_context",
               description="Fetch an account's role, department, and privilege level.",
               inputSchema={"type": "object",
                            "properties": {"user": {"type": "string"}},
                            "required": ["user"]}),
]


def build_soc_server() -> Server:
    server = Server("aegis-soc-tools")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return ADVERTISED

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        fn = TOOLS.get(name)
        if fn is None:
            raise ValueError(f"unknown tool {name}")
        return [types.TextContent(type="text", text=fn(**(arguments or {})))]

    return server


async def discover_and_call(tool: str = "ip_reputation", arguments: dict | None = None):
    """Connect a real client, DISCOVER the tools, then call one."""
    arguments = arguments or {"ip": "203.0.113.42"}
    server = build_soc_server()
    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        listed = await client.list_tools()                   # DISCOVERY
        names = [t.name for t in listed.tools]
        called = await client.call_tool(tool, arguments)
        return names, json.loads(called.content[0].text)


if __name__ == "__main__":
    names, result = asyncio.run(discover_and_call())
    print("mcp — tools discovered at runtime:", names)
    print("nothing about these was hard-coded on the client")
    print(f'\nip_reputation -> {result["verdict"]} (score {result["score"]})')
