"""
§9.6 MCP discovery: the router learns its own routes.

build_capability_server() is a real MCP server (the `mcp` SDK) that advertises
handlers as tools. discover_routes() connects a real client over the in-memory
transport, calls list_tools(), and builds a route table from the descriptions.
Publish a handler server-side and it is routable with no client change.

The cost, stated plainly: the route table now lives in a document you do not
control - which is why Chapter 11 screens every tool description.
"""
import asyncio

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.shared.memory import create_connected_server_and_client_session

from .router import route_with_confidence

DEFAULT_HANDLERS = [
    {"name": "phishing_handler",
     "description": "Handles phishing: suspicious email, malicious url or link, sender, credential harvest."},
    {"name": "auth_handler",
     "description": "Handles authentication: failed login, brute force, account takeover, session, password."},
    {"name": "egress_handler",
     "description": "Handles data exfiltration: egress, outbound transfer, bytes, unusual destination."},
]


def build_capability_server(extra_tools: list | None = None) -> Server:
    handlers = DEFAULT_HANDLERS + list(extra_tools or [])
    server = Server("aegis-capabilities")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [types.Tool(name=h["name"], description=h["description"],
                           inputSchema={"type": "object", "properties": {"alert": {"type": "object"}},
                                        "required": ["alert"]})
                for h in handlers]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=f"{name} accepted alert {arguments.get('alert', {}).get('id')}")]

    return server


async def _discover(server: Server) -> dict:
    async with create_connected_server_and_client_session(server) as client:
        await client.initialize()
        listed = await client.list_tools()
        return {t.name: t.description or "" for t in listed.tools}


def discover_routes(server: Server) -> dict:
    """Ask the server what it can do; return {handler_name: description}.
    Works from a script (asyncio.run) and from a notebook cell (existing loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_discover(server))
    # Inside a running loop (Jupyter/Colab): run the coroutine on a helper thread.
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _discover(server)).result()


def route_via_discovery(alert: dict, routes: dict, min_score: float = 0.15,
                        min_margin: float = 0.05) -> dict:
    """The same confidence-gated router, over a discovered route table."""
    return route_with_confidence(alert, min_score=min_score, min_margin=min_margin, routes=routes)
