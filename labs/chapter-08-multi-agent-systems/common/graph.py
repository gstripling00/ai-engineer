"""
§8.6 The loop as a graph.

The orchestrator in this chapter is a for-loop over three workers, passing an
envelope. LangGraph's StateGraph is the same thing with the envelope as the graph
STATE and the workers as NODES. Nothing about the team changes: the workers, the
tools, the authorization check, and the audit are all imported as they are.

What the graph buys you over the loop is a checkpoint at every node boundary -
a run you can inspect step by step and resume from the node that failed.
"""
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from . import workers
from .a2a import A2AMessage
from .model import get_model


class TeamState(TypedDict, total=False):
    """The envelope's fields, as graph state. Same shape as A2AMessage."""
    task: str
    from_agent: str
    to_agent: str
    payload: dict
    findings: dict
    trace_id: str
    hops: list


def to_state(m: A2AMessage) -> TeamState:
    return {"task": m.task, "from_agent": m.from_agent, "to_agent": m.to_agent,
            "payload": m.payload, "findings": m.findings, "trace_id": m.trace_id, "hops": []}


def from_state(s: TeamState) -> A2AMessage:
    return A2AMessage(task=s["task"], from_agent=s["from_agent"], to_agent=s["to_agent"],
                      payload=dict(s.get("payload", {})), findings=dict(s.get("findings", {})),
                      trace_id=s["trace_id"])


def _node(worker):
    """Wrap a Chapter 8 worker as a graph node: state in, worker runs, state out."""
    def run(state: TeamState) -> TeamState:
        before = state["to_agent"]
        message = worker(from_state(state), get_model())
        return {**to_state(message), "hops": state.get("hops", []) + [f"{before} -> {message.to_agent}"]}
    run.__name__ = worker.__name__
    return run


def build_team_graph(checkpointer=None):
    g = StateGraph(TeamState)
    g.add_node("triage", _node(workers.triage))
    g.add_node("investigate", _node(workers.investigate))
    g.add_node("report", _node(workers.report))
    g.add_edge(START, "triage")            # the loop's order, as edges
    g.add_edge("triage", "investigate")
    g.add_edge("investigate", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)


def run_team_graph(message: A2AMessage, checkpointer=None, thread_id: str = "run-1") -> dict:
    graph = build_team_graph(checkpointer)
    config = {"configurable": {"thread_id": thread_id}} if checkpointer else None
    return graph.invoke(to_state(message), config=config)


def checkpoints(message: A2AMessage, thread_id: str = "history") -> list:
    """Run under a MemorySaver and return one entry per saved state, oldest first."""
    saver = MemorySaver()
    run_team_graph(message, checkpointer=saver, thread_id=thread_id)
    history = list(build_team_graph(saver).get_state_history({"configurable": {"thread_id": thread_id}}))
    history.reverse()
    return [{"step": s.metadata.get("step"), "next": s.next, "to_agent": s.values.get("to_agent")} for s in history]
