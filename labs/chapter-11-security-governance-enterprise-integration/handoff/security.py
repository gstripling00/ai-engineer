"""
Security across the handoff.

Chapter 11 secured one agent. Multi-agent systems have a failure mode a single
agent does not: a poisoned finding that CROSSES a handoff. Investigation reads
an injected log, writes a tainted summary into the envelope, and Reporting acts
on it having never seen the injection. Three controls, all on the envelope:

  provenance   every payload field records where its value came from
  taint check  at each handoff, values derived from untrusted content are
               neutralised (or the handoff is refused) BEFORE the next agent reads them
  signing      an HMAC over the envelope, keyed per sender; a spoofed or altered
               handoff is rejected before the receiving agent does any work

Reuses Chapter 11's scanner and neutraliser and Chapter 8's envelope shape, on
purpose: the controls are the same, the seam moves from the agent to the handoff.
"""
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LABS = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_LABS, "chapter-11-security-governance-enterprise-integration"))
from security.hardening import neutralize, scan_for_injection  # noqa: E402

UNTRUSTED_SOURCES = ("log", "email", "tool_result", "external")


@dataclass
class Field:
    """A value plus where it came from. Provenance is what makes taint checkable."""
    value: object
    source: str                    # "log", "tool_result", "agent:triage", "policy", ...
    tainted: bool = False          # derived from untrusted content that has NOT been neutralised
    neutralised: bool = False

    def to_dict(self) -> dict:
        return {"value": self.value, "source": self.source, "tainted": self.tainted,
                "neutralised": self.neutralised}


@dataclass
class SignedEnvelope:
    task: str
    from_agent: str
    to_agent: str
    trace_id: str
    payload: dict = field(default_factory=dict)      # name -> Field
    signature: str = ""

    def body(self) -> dict:
        return {"task": self.task, "from_agent": self.from_agent, "to_agent": self.to_agent,
                "trace_id": self.trace_id,
                "payload": {k: v.to_dict() for k, v in sorted(self.payload.items())}}


def field_from_untrusted(value: str, source: str) -> Field:
    """Content that arrived from outside the agent system: taint it unless it is clean."""
    return Field(value=value, source=source, tainted=bool(scan_for_injection(str(value))))


def derive(value: object, source_agent: str, *inputs: Field) -> Field:
    """A value an agent computed from other fields inherits their taint."""
    return Field(value=value, source=f"agent:{source_agent}",
                 tainted=any(i.tainted and not i.neutralised for i in inputs))


# ---------------------------------------------------------------- taint check at the handoff

def taint_check(envelope: SignedEnvelope, policy: str = "neutralise") -> dict:
    """Run BEFORE the receiving agent reads the envelope.
    policy='neutralise' defangs tainted string fields and marks them; 'refuse' rejects the handoff."""
    tainted = {k: v for k, v in envelope.payload.items() if v.tainted and not v.neutralised}
    if not tainted:
        return {"ok": True, "tainted_fields": [], "action": "none"}
    if policy == "refuse":
        return {"ok": False, "tainted_fields": sorted(tainted), "action": "refused"}
    for name, f in tainted.items():
        if isinstance(f.value, str):
            f.value = neutralize(f.value)
        f.neutralised = True
    return {"ok": True, "tainted_fields": sorted(tainted), "action": "neutralised"}


# ---------------------------------------------------------------- signing

def _mac(key: bytes, body: dict) -> str:
    return hmac.new(key, json.dumps(body, sort_keys=True, default=str).encode(), hashlib.sha256).hexdigest()


def sign(envelope: SignedEnvelope, keys: dict) -> SignedEnvelope:
    """Sign with the SENDER's key. Each agent holds only its own."""
    envelope.signature = _mac(keys[envelope.from_agent], envelope.body())
    return envelope


def verify(envelope: SignedEnvelope, keys: dict) -> dict:
    """The receiver checks the signature against the claimed sender's key."""
    key = keys.get(envelope.from_agent)
    if key is None:
        return {"ok": False, "reason": f"unknown sender {envelope.from_agent}"}
    expected = _mac(key, envelope.body())
    if not hmac.compare_digest(expected, envelope.signature or ""):
        return {"ok": False, "reason": "signature mismatch - forged sender or altered payload"}
    return {"ok": True, "reason": "verified"}


def receive(envelope: SignedEnvelope, keys: dict, policy: str = "neutralise") -> dict:
    """The receiving agent's gate: verify the sender, then check taint. Both before any work."""
    v = verify(envelope, keys)
    if not v["ok"]:
        return {"accepted": False, "stage": "verify", **v}
    t = taint_check(envelope, policy)
    if not t["ok"]:
        return {"accepted": False, "stage": "taint", "reason": f"tainted fields {t['tainted_fields']}", **t}
    return {"accepted": True, "stage": "ok", **t}


def new_keys(*agents: str) -> dict:
    """Per-agent secrets. In production these come from a secret store, never a cell."""
    return {a: hashlib.sha256(f"demo-key-{a}".encode()).digest() for a in agents}
