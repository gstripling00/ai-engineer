"""
Defenses for four of the five attack surfaces (§11.1.2). One rule runs through
all of them: UNTRUSTED CONTENT IS DATA, NEVER INSTRUCTIONS.

  1 prompt injection      scan_for_injection / neutralize / safe_ingest
  2 tool misuse           IAM_POLICY + authorize        (the reader is not the actor)
  3 data exfiltration     mask_pii                      (a floor, not a ceiling)
  4 model boundary abuse  safety_filter / guarded_model_call, both directions
  5 accountability gaps   AuditLog                      (every decision on the record)

Every text-matching defense here is a pattern matcher, and pattern matchers are
evaded by encoding. That is the point of §11.7: no single layer holds; the stack does.
"""
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- surface 1: injection

INJECTION_PATTERNS = [
    r"ignore (all |any |your |the )?(previous |prior )?(instructions|prompt)",
    r"disregard (the )?(above|previous|system)",
    r"you are now",
    r"mark this (alert )?(as )?(benign|safe|resolved)",
    r"do not (escalate|alert|report)",
    r"system prompt",
    r"</?(system|instruction)>",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def scan_for_injection(untrusted_text: str) -> list:
    """Detection: which injection phrases appear in attacker-controllable text."""
    return [m.group(0) for m in _INJ.finditer(untrusted_text)]


def neutralize(untrusted_text: str) -> str:
    """Control: defang detected phrases AND fence the whole thing as inert data.
    The fence matters even for injections the patterns miss - it changes what the
    content IS, not just whether you noticed it."""
    defanged = _INJ.sub("[REDACTED-INJECTION]", untrusted_text)
    return f"<untrusted_data>\n{defanged}\n</untrusted_data>"


def safe_ingest(log_line: str) -> dict:
    """The guarded path for reading a log line into the agent's context."""
    found = scan_for_injection(log_line)
    return {"injection_detected": bool(found), "phrases": found, "safe_text": neutralize(log_line)}

# ---------------------------------------------------------------- surfaces 2 and 5: IAM + audit

IAM_POLICY = {
    "triage": {"search_logs", "get_user_context"},
    "investigation": {"search_logs", "ip_reputation", "get_user_context"},
    "reporting": {"create_ticket"},
}


@dataclass
class AuditLog:
    entries: list = field(default_factory=list)

    def record(self, agent: str, tool: str, allowed: bool, trace_id: str = "") -> None:
        self.entries.append({"agent": agent, "tool": tool, "allowed": allowed, "trace_id": trace_id})

    def denied(self) -> list:
        return [e for e in self.entries if not e["allowed"]]


def authorize(agent: str, tool: str, audit: AuditLog | None = None, trace_id: str = "") -> bool:
    """A list membership check. The model's opinion is never consulted, and the
    decision - allowed or denied - goes on the record."""
    allowed = tool in IAM_POLICY.get(agent, set())
    if audit is not None:
        audit.record(agent, tool, allowed, trace_id)
    return allowed

# ---------------------------------------------------------------- surface 3: exfiltration

_EMAIL = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")
_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_CRED = re.compile(r"(password|passwd|secret|token|api[_ -]?key)\s*[:=]\s*[^\s.,;]+", re.IGNORECASE)


def mask_pii(text: str, keep_ip: bool = True) -> str:
    """Emails and credentials are never kept. The IP is kept BY DEFAULT because a
    SOC needs it as an indicator - a documented choice, wrong for somebody."""
    out = _EMAIL.sub("<EMAIL>", text)
    out = _CRED.sub(lambda m: re.split(r"[:=]", m.group(0))[0].rstrip() + ": <REDACTED>", out)
    if not keep_ip:
        out = _IPV4.sub("<IP>", out)
    return out

# ---------------------------------------------------------------- surface 4: safety filters

SAFETY_CATEGORIES = {
    "credential_disclosure": ["password is", "here are the credentials", "api key:", "the token is"],
    "harmful_instructions": ["disable all logging", "delete the audit log", "exfiltrate", "cover your tracks"],
}


def safety_filter(text: str, direction: str = "input") -> dict:
    lowered = text.lower()
    fired = sorted({cat for cat, phrases in SAFETY_CATEGORIES.items() if any(p in lowered for p in phrases)})
    return {"direction": direction, "allowed": not fired, "categories": fired}


def guarded_model_call(prompt: str, respond) -> dict:
    """input filter -> model -> output filter. Either side can block, and every
    block names its category so a refusal is an auditable decision."""
    checked_in = safety_filter(prompt, "input")
    if not checked_in["allowed"]:
        return {"blocked_at": "input", "filter": checked_in, "output": None}
    output = respond(prompt)
    checked_out = safety_filter(output, "output")
    if not checked_out["allowed"]:
        return {"blocked_at": "output", "filter": checked_out, "output": None}
    return {"blocked_at": None, "filter": checked_out, "output": output}
