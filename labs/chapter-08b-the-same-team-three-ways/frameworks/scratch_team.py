"""Orchestration 1 — scratch. Chapter 8's loop, verbatim: sequence the specialists and pass the envelope."""
from .team import Result, finish, fresh_run, workers

STAGES = (workers.triage, workers.investigate, workers.report)


def run_scratch(alert: dict, trace_id: str) -> Result:
    message, mark, model = fresh_run(alert, trace_id)
    hops = []
    for stage in STAGES:                                   # <- the whole orchestrator
        before = message.to_agent
        message = stage(message, model)
        hops.append(f"{before} -> {message.to_agent}")
    return finish("scratch", message, hops, mark, orchestration_lines=4)
