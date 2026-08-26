"""
Chapter 8's three workers as real A2A agents (the a2a-sdk, protocol 1.0).

Each worker becomes a server that:
  * publishes an AGENT CARD at /.well-known/agent-card.json - name, skills, and
    which tools it holds - so a client can discover what it does before calling it;
  * accepts a MESSAGE whose data part is Chapter 8's envelope, runs the unchanged
    worker, and returns the next envelope as a data ARTIFACT on a TASK;
  * reports the task's STATE (submitted -> working -> completed) and carries the
    incident's trace id as the protocol's context_id.

The workers, tools, envelope, and authorization checks are imported from Chapter 8.
This module only decides how they are described and how a task travels.
"""
import os
import sys

from fastapi import FastAPI

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers import get_data_parts, new_data_artifact, new_data_message, new_task_from_user_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.fastapi_routes import add_a2a_routes_to_fastapi
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Role, SendMessageRequest, TaskState

_LABS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_LABS, "chapter-08-multi-agent-systems"))
from common import workers                                                    # noqa: E402  Chapter 8
from common.a2a import A2AMessage                                             # noqa: E402
from common.model import get_model                                            # noqa: E402

# ---------------------------------------------------------------- envelope <-> data part

def envelope_to_dict(m: A2AMessage) -> dict:
    return {"task": m.task, "from_agent": m.from_agent, "to_agent": m.to_agent,
            "payload": m.payload, "findings": m.findings, "trace_id": m.trace_id}


def envelope_from_dict(d: dict) -> A2AMessage:
    return A2AMessage(task=d["task"], from_agent=d["from_agent"], to_agent=d["to_agent"],
                      payload=dict(d.get("payload", {})), findings=dict(d.get("findings", {})),
                      trace_id=d["trace_id"])

# ---------------------------------------------------------------- the executor: one per worker

class WorkerExecutor(AgentExecutor):
    """Runs one Chapter 8 worker inside the A2A task lifecycle."""

    def __init__(self, worker):
        self.worker = worker

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)                       # SUBMITTED
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()                                  # WORKING
        try:
            envelope = envelope_from_dict(get_data_parts(context.message.parts)[0])
            nxt = self.worker(envelope, get_model())                # the unchanged worker
            await updater.add_artifact(new_data_artifact("envelope", envelope_to_dict(nxt)).parts, name="envelope")
            await updater.complete()                                # COMPLETED
        except Exception as exc:                                    # FAILED, with the reason on the task
            await updater.failed(message=updater.new_agent_message(
                new_data_message({"error": str(exc)}, role=Role.ROLE_AGENT).parts))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass

# ---------------------------------------------------------------- agent cards

SPECS = {
    "triage": (workers.triage, "Reads logs and the directory to decide whether an alert is a true positive.",
               workers.TRIAGE_TOOLS),
    "investigation": (workers.investigate, "Adds threat-intel reputation and egress evidence; reaches a verdict.",
                      workers.INVEST_TOOLS),
    "reporting": (workers.report, "Opens the ticket. The ONLY agent that writes to the world.",
                  workers.REPORT_TOOLS),
}


def make_card(name: str, url: str) -> AgentCard:
    _worker, description, tools = SPECS[name]
    return AgentCard(
        name=name, description=description, version="1.0",
        supported_interfaces=[AgentInterface(url=url, protocol_binding="JSONRPC", protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["application/json"], default_output_modes=["application/json"],
        skills=[AgentSkill(id=f"{name}-alert", name=f"{name} an Aegis alert", description=description,
                           tags=["soc", "aegis"] + [f"tool:{t}" for t in tools])],
    )


def build_agent_app(name: str, url: str) -> FastAPI:
    """A complete A2A server for one worker: card route + JSON-RPC route on a FastAPI app."""
    worker = SPECS[name][0]
    card = make_card(name, url)
    handler = DefaultRequestHandler(agent_executor=WorkerExecutor(worker), task_store=InMemoryTaskStore(),
                                    agent_card=card)
    app = FastAPI(title=f"aegis-{name}")
    add_a2a_routes_to_fastapi(app, agent_card_routes=create_agent_card_routes(card),
                              jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/"))
    return app

# ---------------------------------------------------------------- the client side

async def discover(http, base_url: str) -> AgentCard:
    """Fetch the agent card. The client knows a URL; everything else it learns here."""
    return await A2ACardResolver(http, base_url).get_agent_card()


async def send_envelope(http, card: AgentCard, envelope: A2AMessage) -> dict:
    """Send the envelope as a task; return the completed task's envelope plus protocol facts."""
    client = ClientFactory(ClientConfig(httpx_client=http, streaming=False)).create(card)
    request = SendMessageRequest(message=new_data_message(envelope_to_dict(envelope),
                                                          context_id=envelope.trace_id, role=Role.ROLE_USER))
    final = None
    async for response in client.send_message(request):
        if response.HasField("task"):
            final = response.task
    if final is None:
        raise RuntimeError(f"{card.name}: no task in response")
    state = TaskState.Name(final.status.state)
    if state != "TASK_STATE_COMPLETED":
        raise RuntimeError(f"{card.name}: task ended in {state}")
    artifact = next(a for a in final.artifacts if a.name == "envelope")
    return {"task_id": final.id, "context_id": final.context_id, "state": state,
            "envelope": envelope_from_dict(get_data_parts(artifact.parts)[0])}
