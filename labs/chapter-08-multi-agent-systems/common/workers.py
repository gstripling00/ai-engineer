"""
Three specialists. Each has a LIST of permitted tools, and authorized_call()
checks the list before dispatching anything. The model's opinion is never
consulted: a manipulated Triage agent can decide it wants to open a ticket, and
list membership stops it.

    Triage         search_logs, get_user_context           reads
    Investigation  + ip_reputation                          reads
    Reporting      create_ticket                            the only writer

Each worker takes the incoming envelope, does its job, fills in findings, and
returns the NEXT envelope (the handoff), trace id carried forward.
"""
import json

from . import soc
from .a2a import A2AMessage

TRIAGE_TOOLS = ["search_logs", "get_user_context"]
INVEST_TOOLS = ["search_logs", "ip_reputation", "get_user_context"]
REPORT_TOOLS = ["create_ticket"]

PERMITTED = {"triage": TRIAGE_TOOLS, "investigation": INVEST_TOOLS, "reporting": REPORT_TOOLS}

AUDIT: list = []


def authorized_call(role: str, tool: str, args: dict, trace_id: str = "") -> str:
    """Dispatch only if this role is permitted this tool. Every attempt is audited."""
    allowed = tool in PERMITTED.get(role, [])
    AUDIT.append({"trace_id": trace_id, "role": role, "tool": tool, "allowed": allowed})
    if not allowed:
        return json.dumps({"error": f"{role} is not permitted to call {tool}", "denied": True})
    return soc.TOOLS[tool](**args)


def triage(message: A2AMessage, model=None) -> A2AMessage:
    alert = message.payload["alert"]
    logs = json.loads(authorized_call("triage", "search_logs", {"query": alert["user"]}, message.trace_id))
    user = json.loads(authorized_call("triage", "get_user_context", {"user": alert["user"]}, message.trace_id))
    failures = [e for e in logs["results"] if e["event"] == "auth_fail"]
    success = [e for e in logs["results"] if e["event"] == "auth_success"]
    true_positive = len(failures) >= 2 and len(success) >= 1
    message.findings = {"alert": alert, "true_positive": true_positive,
                        "user_role": user.get("role"), "privileged": user.get("privileged", False),
                        "preliminary_severity": "high" if true_positive else "low"}
    return message.handoff("investigation", "investigate_alert")


def investigate(message: A2AMessage, model=None) -> A2AMessage:
    alert = message.payload["alert"]
    rep = json.loads(authorized_call("investigation", "ip_reputation", {"ip": alert["src_ip"]}, message.trace_id))
    logs = json.loads(authorized_call("investigation", "search_logs", {"query": "file_download"}, message.trace_id))
    malicious = rep.get("verdict") == "malicious"
    egress = logs["count"] > 0
    message.findings = {**message.payload,
                        "verdict": "confirmed_compromise" if malicious else "inconclusive",
                        "severity": "critical" if (malicious and egress) else "high",
                        "evidence": {"ip_verdict": rep.get("verdict"), "egress_observed": egress}}
    return message.handoff("reporting", "open_ticket")


def report(message: A2AMessage, model=None) -> A2AMessage:
    findings = message.payload
    summary = model.summarize(findings) if model else json.dumps(findings.get("evidence", {}))
    ticket = json.loads(authorized_call("reporting", "create_ticket", {
        "title": f'{findings.get("verdict", "unknown")} on {findings["alert"]["user"]}',
        "severity": findings.get("severity", "medium"),
        "summary": summary}, message.trace_id))
    message.findings = {**findings, "ticket": ticket}
    return message.handoff("orchestrator", "close_investigation")
