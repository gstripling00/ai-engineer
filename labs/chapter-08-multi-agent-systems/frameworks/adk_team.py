"""
Orchestration 3 — Google ADK 2.x. A Workflow whose NODES ARE THE WORKERS and whose
session state carries the envelope.

`@node` turns a plain async function into a workflow node; edges from START through
the three workers define the order. The runner is in-memory, so this runs offline.
What ADK adds for free: per-node retry and timeout configuration, and a scheduler
that runs independent nodes concurrently (see fan_out_workflow).
"""
import asyncio
import concurrent.futures

from google.adk import Workflow
from google.adk.runners import InMemoryRunner
from google.adk.workflow import START, JoinNode, node
from google.genai import types

from .team import Result, envelope_from_dict, envelope_to_dict, finish, fresh_run, get_model, workers


def _worker_node(worker):
    async def run(ctx, node_input):
        state = ctx.state.get("envelope")
        before = state["to_agent"]
        message = worker(envelope_from_dict(state), get_model())
        ctx.state["envelope"] = envelope_to_dict(message)
        ctx.state["hops"] = ctx.state.get("hops", []) + [f"{before} -> {message.to_agent}"]
        return {"to_agent": message.to_agent}
    run.__name__ = worker.__name__
    return node(run, name=worker.__name__)


def build_workflow() -> Workflow:
    triage, investigate, report = (_worker_node(w) for w in (workers.triage, workers.investigate, workers.report))
    return Workflow(name="aegis_team", edges=[(START, triage), (triage, investigate), (investigate, report)])


async def _run(workflow: Workflow, initial_state: dict) -> dict:
    runner = InMemoryRunner(agent=workflow, app_name="aegis")
    session = await runner.session_service.create_session(app_name="aegis", user_id="soc", state=initial_state)
    async for _event in runner.run_async(user_id="soc", session_id=session.id,
                                         new_message=types.Content(role="user", parts=[types.Part(text="run")])):
        pass
    final = await runner.session_service.get_session(app_name="aegis", user_id="soc", session_id=session.id)
    return dict(final.state)


def _sync(coro):
    """asyncio.run() from a script; a helper thread when a loop is already running (notebooks)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def run_adk(alert: dict, trace_id: str) -> Result:
    message, mark, _model = fresh_run(alert, trace_id)
    state = _sync(_run(build_workflow(), {"envelope": envelope_to_dict(message), "hops": []}))
    return finish("adk", envelope_from_dict(state["envelope"]), state["hops"], mark, orchestration_lines=5)


def fan_out_workflow(signals: list, investigator) -> dict:
    """Chapter 8's scatter-gather as an ADK graph: one node per signal, a JoinNode, a merge."""
    def branch(signal):
        async def run(ctx, node_input):
            return {"signal": signal, **investigator(signal)}
        run.__name__ = "branch_" + "".join(ch if ch.isalnum() else "_" for ch in signal)
        return node(run, name=run.__name__)

    async def merge(ctx, node_input):
        verdicts = sorted({v["verdict"] for v in node_input.values()})
        ctx.state["merged"] = {"branches": len(node_input), "distinct_verdicts": verdicts, "dissent": len(verdicts) > 1}
        return ctx.state["merged"]

    branches = [branch(s) for s in signals]
    join = JoinNode(name="join")
    edges = [(START, b) for b in branches] + [(b, join) for b in branches] + [(join, node(merge, name="merge"))]
    state = _sync(_run(Workflow(name="fan_out", edges=edges), {}))
    return state["merged"]
