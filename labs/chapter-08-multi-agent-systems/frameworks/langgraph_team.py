"""
Orchestration 2 — LangGraph. A StateGraph whose STATE IS THE ENVELOPE.

Each node is a thin wrapper: rebuild the A2AMessage from state, call the Chapter 8
worker, write the returned envelope back. The graph decides who runs next; the
worker decides what to do. What LangGraph adds for free: a checkpointer, so a run
can be inspected step by step and resumed from any node.
"""
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .team import (Result, envelope_from_dict, envelope_to_dict, finish, fresh_run, get_model,
                   workers)


class TeamState(TypedDict, total=False):
    task: str
    from_agent: str
    to_agent: str
    payload: dict
    findings: dict
    trace_id: str
    hops: list


def _node(worker):
    def run(state: TeamState) -> TeamState:
        before = state["to_agent"]
        message = worker(envelope_from_dict(state), get_model())
        return {**envelope_to_dict(message), "hops": state.get("hops", []) + [f"{before} -> {message.to_agent}"]}
    run.__name__ = worker.__name__
    return run


def build_graph(checkpointer=None):
    g = StateGraph(TeamState)
    g.add_node("triage", _node(workers.triage))
    g.add_node("investigate", _node(workers.investigate))
    g.add_node("report", _node(workers.report))
    g.add_edge(START, "triage")
    g.add_edge("triage", "investigate")
    g.add_edge("investigate", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)


def run_langgraph(alert: dict, trace_id: str, checkpointer=None, thread_id: str = "run-1") -> Result:
    message, mark, _model = fresh_run(alert, trace_id)
    graph = build_graph(checkpointer)
    config = {"configurable": {"thread_id": thread_id}} if checkpointer else None
    final = graph.invoke({**envelope_to_dict(message), "hops": []}, config=config)
    return finish("langgraph", envelope_from_dict(final), final["hops"], mark, orchestration_lines=9)


def checkpoint_history(alert: dict, trace_id: str) -> list:
    """Run under a MemorySaver and return the checkpointed states, oldest first."""
    saver = MemorySaver()
    run_langgraph(alert, trace_id, checkpointer=saver, thread_id="history")
    graph = build_graph(saver)
    history = list(graph.get_state_history({"configurable": {"thread_id": "history"}}))
    history.reverse()
    return [{"step": s.metadata.get("step"), "next": s.next, "to_agent": s.values.get("to_agent"),
             "keys": sorted(s.values.get("payload", {}))[:3]} for s in history]
