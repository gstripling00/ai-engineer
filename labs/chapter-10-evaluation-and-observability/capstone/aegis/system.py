"""
AegisV12: the assembled system, in miniature.

Every chapter's component in one pipeline, each recorded as a STRUCTURED stage
with attributes rather than a printed string. That decision is what makes the
tracing section a mapping instead of a rewrite: the OpenTelemetry exporter
reads the same data the run already recorded.

    guarded_ingest   Ch 11   screen the raw log for prompt injection
    routed           Ch 9    semantic route (a guess) + severity policy (never a model)
    memory_recall    Ch 5    prior incidents from the same sender/IP
    triage           Ch 1-2  read-only tools, authorized per role
    investigation    Ch 7    reputation + egress, authorized per role
    reported         Ch 8    the one agent that may write

The capstone (Chapter 13) grows this class; the shape does not change.
"""
import json
import re
import uuid
from dataclasses import dataclass, field

from common import soc

PERMITTED = {"triage": ["search_logs", "get_user_context"],
             "investigation": ["search_logs", "ip_reputation", "get_user_context"],
             "reporting": ["create_ticket"]}

INJECTION_PATTERNS = [r"ignore (all |any )?(previous|prior) instructions", r"mark (this|it) (as )?benign",
                      r"disregard (the )?(above|previous)", r"you are now", r"system prompt"]

STAGE_CHAPTER = {"guarded_ingest": "11", "routed": "9", "memory_recall": "5",
                 "triage": "1-2", "investigation": "7", "reported": "8"}


@dataclass
class Run:
    trace_id: str
    alert: dict
    stages: list = field(default_factory=list)   # (stage, attributes)
    audit: list = field(default_factory=list)    # (agent, tool, allowed)
    injection_detected: bool = False
    escalated: bool = False
    findings: dict = field(default_factory=dict)
    ticket: dict | None = None

    def stage(self, name: str, **attributes) -> None:
        self.stages.append((name, {"aegis.chapter": STAGE_CHAPTER.get(name, ""), **attributes}))


class AegisV12:
    """The assembled agent. handle() runs one alert end to end and returns a Run."""

    def __init__(self, memory: list | None = None):
        self.memory = memory if memory is not None else []

    # ---- authorization: a list membership check, audited, never the model's opinion
    def _call(self, run: Run, agent: str, tool: str, args: dict) -> dict:
        allowed = tool in PERMITTED.get(agent, [])
        run.audit.append((agent, tool, allowed))
        if not allowed:
            return {"error": f"{agent} may not call {tool}", "denied": True}
        return json.loads(soc.TOOLS[tool](**args))

    def handle(self, alert: dict, raw_log: str = "") -> Run:
        run = Run(trace_id=f"inc-{uuid.uuid4().hex[:8]}", alert=alert)

        # Ch 11 - guarded ingest: data that talks like an instruction is flagged, not obeyed
        hits = [p for p in INJECTION_PATTERNS if re.search(p, raw_log, re.I)]
        run.injection_detected = bool(hits)
        run.stage("guarded_ingest", injection_detected=run.injection_detected,
                  patterns_matched=len(hits), raw_log_chars=len(raw_log))

        # Ch 9 - routing: kind may be guessed, severity is policy
        rule = alert.get("rule", "").lower()
        route = ("auth_handler" if "login" in rule or "brute" in rule
                 else "phishing_handler" if "phish" in rule else "generalist_handler")
        severity = alert.get("severity_hint", "medium")
        needs_human = severity in ("high", "critical")
        run.stage("routed", route=route, severity=severity, severity_route="human_analyst" if needs_human else "auto_handler")

        # Ch 5 - memory
        prior = [m for m in self.memory if m.get("src_ip") == alert.get("src_ip")]
        run.stage("memory_recall", prior_incidents=len(prior), is_campaign=len(prior) >= 2)

        # Ch 1-2 - triage (read-only)
        logs = self._call(run, "triage", "search_logs", {"query": alert["user"]})
        user = self._call(run, "triage", "get_user_context", {"user": alert["user"]})
        self._call(run, "triage", "create_ticket", {"title": "x", "severity": "low", "summary": ""})  # denied, audited
        fails = sum(1 for e in logs.get("results", []) if e["event"] == "auth_fail")
        succ = sum(1 for e in logs.get("results", []) if e["event"] == "auth_success")
        run.findings.update({"true_positive": fails >= 2 and succ >= 1, "privileged": user.get("privileged", False)})
        run.stage("triage", auth_failures=fails, auth_success=succ, privileged=run.findings["privileged"])

        # Ch 7 - investigation
        rep = self._call(run, "investigation", "ip_reputation", {"ip": alert["src_ip"]})
        egress = self._call(run, "investigation", "search_logs", {"query": "file_download"})
        malicious = rep.get("verdict") == "malicious"
        run.findings.update({"ip_verdict": rep.get("verdict"), "egress_observed": egress.get("count", 0) > 0,
                             "verdict": "confirmed_compromise" if malicious else "inconclusive",
                             "severity": "critical" if malicious and egress.get("count", 0) else "high"})
        run.stage("investigation", ip_verdict=rep.get("verdict"), egress_observed=run.findings["egress_observed"],
                  verdict=run.findings["verdict"])

        # Ch 8 - reporting: the only writer. Injection or privilege -> a human decides.
        run.escalated = run.injection_detected or run.findings["privileged"] or needs_human
        ticket = self._call(run, "reporting", "create_ticket", {
            "title": f'{run.findings["verdict"]} on {alert["user"]}',
            "severity": run.findings["severity"],
            "summary": json.dumps({"escalated": run.escalated, "injection_detected": run.injection_detected})})
        run.ticket = ticket
        run.stage("reported", ticket_id=ticket.get("id", ""), severity=run.findings["severity"], escalated=run.escalated)

        self.memory.append({"src_ip": alert.get("src_ip"), "user": alert.get("user"), "trace_id": run.trace_id})
        return run
