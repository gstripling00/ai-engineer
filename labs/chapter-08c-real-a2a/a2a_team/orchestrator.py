"""
The orchestrator: knows three URLs, discovers three agents, runs one incident.

Everything the orchestrator learns about an agent comes from its card. The
handoff order comes from the envelope's to_agent, exactly as in Chapter 8; the
orchestrator just looks up which discovered agent has that name.

run_in_process() mounts the three FastAPI apps on an httpx ASGI transport, so the
whole protocol runs offline inside one process - the same technique CI uses for
the Chapter 12B service. Swap the transport for real URLs and nothing else changes.
"""
import asyncio
import concurrent.futures

import httpx

from .agents import build_agent_app, discover, send_envelope, workers
from common import soc
from common.a2a import new_investigation

AGENT_URLS = {"triage": "http://triage", "investigation": "http://investigation", "reporting": "http://reporting"}


class MultiAppTransport(httpx.AsyncBaseTransport):
    """Route each request to the in-process app for its host. Stands in for the network."""

    def __init__(self, apps: dict):
        self.transports = {host: httpx.ASGITransport(app=app) for host, app in apps.items()}

    async def handle_async_request(self, request):
        return await self.transports[request.url.host].handle_async_request(request)


async def run_incident(http, alert: dict, trace_id: str, urls: dict = AGENT_URLS) -> dict:
    cards = {name: await discover(http, url) for name, url in urls.items()}      # DISCOVERY
    envelope = new_investigation(alert, trace_id)
    hops, tasks = [], []
    while envelope.to_agent in cards:                                             # the envelope says who is next
        card = cards[envelope.to_agent]
        result = await send_envelope(http, card, envelope)
        hops.append(f"{envelope.to_agent} -> {result['envelope'].to_agent}")
        tasks.append({"agent": card.name, "task_id": result["task_id"], "context_id": result["context_id"],
                      "state": result["state"]})
        envelope = result["envelope"]
    return {"cards": cards, "hops": hops, "tasks": tasks, "final": envelope}


async def run_in_process_async(alert: dict, trace_id: str) -> dict:
    apps = {url.split("//")[1]: build_agent_app(name, url + "/") for name, url in AGENT_URLS.items()}
    soc.reset_tickets()
    mark = len(workers.AUDIT)
    async with httpx.AsyncClient(transport=MultiAppTransport(apps)) as http:
        out = await run_incident(http, alert, trace_id)
    out["audit"] = [(e["role"], e["tool"], e["allowed"]) for e in workers.AUDIT[mark:]]
    return out


def run_in_process(alert: dict, trace_id: str) -> dict:
    """asyncio.run() from a script; a helper thread when a loop is already running (notebooks)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_in_process_async(alert, trace_id))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, run_in_process_async(alert, trace_id)).result()
