"""
The team is Chapter 8's, imported from its own folder. Nothing here re-implements
a worker, a tool, or an authorization check; the three orchestrators below only
decide WHO RUNS NEXT and WHAT STATE CARRIES BETWEEN THEM.

    scratch    a for-loop over the three workers (Chapter 8, verbatim)
    LangGraph  a StateGraph whose state is the envelope
    ADK        a Workflow whose nodes are the workers and whose session state is the envelope

run_scratch / run_langgraph / run_adk all return the same Result, so the notebook
can compare them field by field.
"""
import os
import sys
from dataclasses import dataclass, field

_LABS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_LABS, "chapter-08-multi-agent-systems"))
from common import soc, workers                       # noqa: E402  Chapter 8, unchanged
from common.a2a import A2AMessage, new_investigation  # noqa: E402
from common.model import get_model                    # noqa: E402


@dataclass
class Result:
    framework: str
    trace_id: str
    verdict: str
    severity: str
    ticket_id: str
    hops: list = field(default_factory=list)     # (from_agent -> to_agent) per handoff
    audit: list = field(default_factory=list)    # (agent, tool, allowed), this run only
    orchestration_lines: int = 0                 # lines of code that decide who runs next


def envelope_to_dict(m: A2AMessage) -> dict:
    return {"task": m.task, "from_agent": m.from_agent, "to_agent": m.to_agent,
            "payload": m.payload, "findings": m.findings, "trace_id": m.trace_id}


def envelope_from_dict(d: dict) -> A2AMessage:
    return A2AMessage(task=d["task"], from_agent=d["from_agent"], to_agent=d["to_agent"],
                      payload=dict(d.get("payload", {})), findings=dict(d.get("findings", {})),
                      trace_id=d["trace_id"])


def fresh_run(alert: dict, trace_id: str):
    """Reset the world, mark the audit watermark, open the envelope."""
    soc.reset_tickets()
    return new_investigation(alert, trace_id), len(workers.AUDIT), get_model()


def finish(framework: str, final: A2AMessage, hops: list, audit_start: int, orchestration_lines: int) -> Result:
    p = final.payload
    return Result(framework=framework, trace_id=final.trace_id, verdict=p.get("verdict", "?"),
                  severity=p.get("severity", "?"), ticket_id=p.get("ticket", {}).get("id", "?"),
                  hops=hops, audit=[(e["role"], e["tool"], e["allowed"]) for e in workers.AUDIT[audit_start:]],
                  orchestration_lines=orchestration_lines)
