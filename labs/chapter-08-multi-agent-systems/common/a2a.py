"""
Agent-to-agent messages: a typed envelope, not a blob of text.

The field doing the heavy lifting is trace_id. It is constant across the whole
incident, so three independent agents become ONE auditable investigation. When
someone asks six months later why an account got locked, the answer is a query,
not an archaeology project.
"""
from dataclasses import dataclass, field


@dataclass
class A2AMessage:
    task: str                                     # what the receiver must do
    from_agent: str
    to_agent: str
    payload: dict = field(default_factory=dict)   # structured inputs
    findings: dict = field(default_factory=dict)  # structured outputs
    trace_id: str = ""

    def handoff(self, to_agent: str, task: str, **payload) -> "A2AMessage":
        """The next message in the chain, carrying the trace id forward."""
        return A2AMessage(task=task, from_agent=self.to_agent, to_agent=to_agent,
                          payload={**self.findings, **payload}, trace_id=self.trace_id)


def new_investigation(alert: dict, trace_id: str) -> A2AMessage:
    return A2AMessage(task="triage_alert", from_agent="orchestrator", to_agent="triage",
                      payload={"alert": alert}, trace_id=trace_id)
