"""
AegisV12: the assembled system. Every chapter's component in one pipeline.

Each stage is recorded as a STRUCTURED span - a dict with a stage name, a
timestamp, the incident's trace_id, and attributes - never a printed string.
That is what lets Chapter 10 map the run onto OpenTelemetry without a rewrite,
and what lets Chapter 13's analyst interface render from the real run.

    received         Ch 1     the alert arrives; the trace begins
    guarded_ingest   Ch 11    untrusted content is data, never instructions
    routed           Ch 9     kind may be guessed; severity is policy
    memory_recall    Ch 5     prior incidents from the same source
    triage           Ch 8     read-only, authorized per role, audited
    investigation    Ch 8     reputation + egress, authorized per role
    escalated        Ch 9     the reasons a human must decide
    reported         Ch 8+11  the only agent that writes; the summary is PII-masked
    done             -        the trace closes

handle() returns a Run: a dict of findings (what the notebooks index) with
attribute access for the tracer (what Chapter 10's exporter reads).
"""
import json
import re
import time
import uuid

from common import soc
from common.model import get_model

PERMITTED = {"triage": ["search_logs", "get_user_context"],
             "investigation": ["search_logs", "ip_reputation", "get_user_context"],
             "reporting": ["create_ticket"]}

INJECTION_PATTERNS = [
    r"ignore (all |any |your |the )?(previous |prior )?(instructions|prompt)",
    r"disregard (the )?(above|previous|system)",
    r"you are now",
    r"mark this (alert )?(as )?(benign|safe|resolved)",
    r"do not (escalate|alert|report)",
    r"system prompt",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
_EMAIL = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")
_CRED = re.compile(r"(password|passwd|secret|token)\s*[:=]\s*[^\s.,;]+", re.IGNORECASE)

STAGE_CHAPTER = {"received": "1", "guarded_ingest": "11", "routed": "9", "memory_recall": "5",
                 "triage": "8", "investigation": "8", "escalated": "9", "reported": "8+11", "done": ""}


def mask_pii(text: str) -> str:
    out = _EMAIL.sub("<EMAIL>", text)
    return _CRED.sub(lambda m: re.split(r"[:=]", m.group(0))[0].rstrip() + ": <REDACTED>", out)


class Run(dict):
    """Findings dict (indexable) with attribute views for the OpenTelemetry exporter."""

    @property
    def trace_id(self): return self["trace_id"]
    @property
    def alert(self): return self["alert"]
    @property
    def injection_detected(self): return self["injection_detected"]
    @property
    def escalated(self): return self["escalated"]
    @property
    def ticket(self): return self["ticket"]
    @property
    def stages(self):
        return [(s["stage"], {"aegis.chapter": STAGE_CHAPTER.get(s["stage"], ""),
                              **{k: v for k, v in s.items() if k not in ("stage", "t", "trace_id")}})
                for s in self["trace"]]
    @property
    def audit(self):
        return [(e["agent"], e["tool"], e["allowed"]) for e in self["audit"]]


class AegisV12:
    """The assembled agent. handle() runs one alert end to end and returns a Run."""

    def __init__(self, memory: list | None = None):
        self.memory = memory if memory is not None else []
        self.model = get_model()

    # ---- the seam every stage writes through
    @staticmethod
    def _span(run: Run, stage: str, **attrs) -> None:
        run["trace"].append({"stage": stage, "t": round(time.time() % 1000, 3),
                             "trace_id": run["trace_id"], **attrs})

    # ---- authorization: a list membership check, audited, never the model's opinion
    @staticmethod
    def _call(run: Run, agent: str, tool: str, args: dict) -> dict:
        allowed = tool in PERMITTED.get(agent, [])
        run["audit"].append({"agent": agent, "tool": tool, "allowed": allowed, "trace_id": run["trace_id"]})
        if not allowed:
            return {"error": f"{agent} may not call {tool}", "denied": True}
        return json.loads(soc.TOOLS[tool](**args))

    def handle(self, alert: dict, raw_log: str = "") -> Run:
        run = Run(trace_id=f"inc-{uuid.uuid4().hex[:8]}", alert=alert, trace=[], audit=[],
                  model_tier=self.model.name)
        self._span(run, "received", alert_id=alert.get("id", ""), rule=alert.get("rule", ""))

        # Ch 11 - guarded ingest
        phrases = [m.group(0) for m in _INJ.finditer(raw_log)]
        run["injection_detected"] = bool(phrases)
        run["safe_log"] = f"<untrusted_data>{_INJ.sub('[REDACTED-INJECTION]', raw_log)}</untrusted_data>"
        self._span(run, "guarded_ingest", injection_detected=run["injection_detected"], phrases=phrases)

        # Ch 9 - routing
        rule = alert.get("rule", "").lower()
        route = ("auth_handler" if any(k in rule for k in ("login", "brute", "auth"))
                 else "phishing_handler" if "phish" in rule
                 else "egress_handler" if any(k in rule for k in ("egress", "exfil", "transfer"))
                 else "generalist_handler")
        severity_in = alert.get("severity_hint") or alert.get("severity") or "medium"
        self._span(run, "routed", route=route, severity_in=severity_in,
                   severity_route="human_analyst" if severity_in in ("high", "critical") else "auto_handler")

        # Ch 5 - memory
        prior = [m for m in self.memory if m.get("src_ip") == alert.get("src_ip")]
        self._span(run, "memory_recall", prior_incidents=len(prior), is_campaign=len(prior) >= 2)

        # Ch 8 - triage (read-only)
        logs = self._call(run, "triage", "search_logs", {"query": alert.get("user", "")})
        user = self._call(run, "triage", "get_user_context", {"user": alert.get("user", "")})
        self._call(run, "triage", "create_ticket", {"title": "x", "severity": "low", "summary": ""})  # denied, audited
        fails = sum(1 for e in logs.get("results", []) if e["event"] == "auth_fail")
        succ = sum(1 for e in logs.get("results", []) if e["event"] == "auth_success")
        privileged = bool(user.get("privileged", False))
        self._span(run, "triage", auth_failures=fails, auth_success=succ, role=user.get("role"),
                   privileged=privileged, true_positive=fails >= 2 and succ >= 1)

        # Ch 8 - investigation
        rep = self._call(run, "investigation", "ip_reputation", {"ip": alert.get("src_ip", "")})
        egress = self._call(run, "investigation", "search_logs", {"query": "file_download"})
        malicious = rep.get("verdict") == "malicious"
        egress_seen = egress.get("count", 0) > 0
        run["verdict"] = "confirmed_compromise" if malicious else "inconclusive"
        run["severity"] = "critical" if (malicious and egress_seen) else "high" if malicious else severity_in
        run["evidence"] = {"ip_verdict": rep.get("verdict"), "ip_score": rep.get("score"),
                           "egress_observed": egress_seen, "auth_failures": fails, "prior_incidents": len(prior)}
        self._span(run, "investigation", ip_verdict=rep.get("verdict"), egress_observed=egress_seen,
                   verdict=run["verdict"], severity=run["severity"])

        # Ch 9 - escalation: policy, with reasons
        reasons = []
        if run["injection_detected"]: reasons.append("injection attempt in source data")
        if privileged: reasons.append("privileged account")
        if run["severity"] in ("high", "critical"): reasons.append(f"severity {run['severity']} requires human review")
        run["escalated"] = bool(reasons)
        run["escalation_reasons"] = reasons
        run["open_questions"] = ["was any other account accessed from this IP?"] if malicious else []
        self._span(run, "escalated", escalated=run["escalated"], reasons=reasons)

        # Ch 8 + 11 - reporting: the only writer; the summary is masked before it leaves
        summary = mask_pii(self.model.summarize({"alert": alert, "verdict": run["verdict"],
                                                 "evidence": run["evidence"]}))
        ticket = self._call(run, "reporting", "create_ticket", {
            "title": f'{run["verdict"]} on {alert.get("user", "?")}',
            "severity": run["severity"], "summary": summary})
        run["ticket"] = ticket
        self._span(run, "reported", ticket_id=ticket.get("id", ""), severity=run["severity"],
                   summary_masked=True)

        self.memory.append({"src_ip": alert.get("src_ip"), "user": alert.get("user"), "trace_id": run["trace_id"]})
        self._span(run, "done", stages=len(run["trace"]) + 1, tool_calls=len(run["audit"]))
        return run
