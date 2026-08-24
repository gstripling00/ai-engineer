#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 8 sample notebook.

Same contract as the earlier samples: no repo clone, no pip install, no API key.
Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 8's claim: multi-agent is not about intelligence. It is about privilege
and auditability. Three specialists with three toolsets means exactly one agent
can write to the world, and every handoff is a typed, traceable envelope.

    python tools/make_sample_ch8.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch08", "Aegis_Chapter8_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 8 — Multi-Agent Systems",
       "",
       "Until now Aegis has been one agent doing everything: reading logs, checking",
       "reputation, deciding, reporting. It works. It also means a single agent holds every",
       "tool you own — including the ones that change the world.",
       "",
       "Splitting Aegis into a team is usually sold as a capability story: specialists",
       "outperform generalists. That is true, and it is the *less* important half.",
       "",
       "The important half is this: **three specialists with three toolsets means exactly one",
       "agent can write to the world.** Least privilege stops being a policy you write down",
       "and becomes the org chart.",
       "",
       "| Agent | Tools | May write? |",
       "|---|---|---|",
       "| **Triage** | search_logs, get_user_context | no |",
       "| **Investigation** | search_logs, ip_reputation, get_user_context | no |",
       "| **Reporting** | create_ticket | **yes** |",
       "",
       "This notebook builds that team, hands work between them with typed envelopes, and",
       "then tries to break the privilege boundary on purpose.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## The tools, and who may hold them",
       "",
       "Four tools. Three of them read. One of them acts.",
       "",
       "`create_ticket` is the only function here that changes anything outside the agent —",
       "it appends to a store, and in production it would page a human, open a case, or",
       "trigger a containment workflow. Everything downstream of this notebook depends on",
       "which agent is allowed to call it."),
    code('''import json
import uuid
from dataclasses import dataclass, field, asdict

LOGS = [
    {"ts": "09:12:04", "event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:12:41", "event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:13:02", "event": "auth_success", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:31:55", "event": "file_download", "user": "j.okafor", "bytes": 8400000},
]

REPUTATION = {"203.0.113.42": {"score": 92, "verdict": "malicious",
                               "categories": ["bruteforce", "c2"]}}

DIRECTORY = {"j.okafor": {"role": "Finance Analyst", "privileged": False}}

TICKETS = []

ALERT = {"id": "ALERT-7731", "rule": "Multiple failed logins followed by success",
         "user": "j.okafor", "src_ip": "203.0.113.42", "severity_hint": "high"}


def search_logs(query: str, window: str = "1h") -> str:
    q = query.lower()
    hits = [l for l in LOGS if q in l["event"].lower() or q in l.get("user", "").lower()]
    return json.dumps({"count": len(hits), "results": hits})


def ip_reputation(ip: str) -> str:
    rep = REPUTATION.get(ip, {"score": 0, "verdict": "unknown"})
    return json.dumps({"ip": ip, **rep})


def get_user_context(user: str) -> str:
    return json.dumps({"user": user, **DIRECTORY.get(user, {"role": "unknown"})})


def create_ticket(title: str, severity: str, summary: str) -> str:
    """The ONLY tool here that changes the world."""
    ticket = {"id": f"INC-{1000 + len(TICKETS) + 1}", "title": title,
              "severity": severity, "summary": summary, "status": "open"}
    TICKETS.append(ticket)
    return json.dumps(ticket)


TOOLS = {"search_logs": search_logs, "ip_reputation": ip_reputation,
         "get_user_context": get_user_context, "create_ticket": create_ticket}

print("tools:", list(TOOLS))
print("world-changing:", ["create_ticket"])'''),

    md("## Least privilege, as data",
       "",
       "Each worker's permitted tools are a list. Not a comment, not a prompt instruction —",
       "a list that a function checks before dispatching anything.",
       "",
       "This is the entire security property of the chapter, and it is six lines. Notice that",
       "Triage cannot open a ticket even if it decides it wants to: the authorization check",
       "does not consult the agent's opinion."),
    code('''TRIAGE_TOOLS = ["search_logs", "get_user_context"]
INVEST_TOOLS = ["search_logs", "ip_reputation", "get_user_context"]
REPORT_TOOLS = ["create_ticket"]

PERMITTED = {"triage": TRIAGE_TOOLS,
             "investigation": INVEST_TOOLS,
             "reporting": REPORT_TOOLS}

AUDIT = []


def authorized_call(role: str, tool: str, args: dict) -> str:
    """Dispatch a tool call only if this role is permitted to make it."""
    allowed = tool in PERMITTED.get(role, [])
    AUDIT.append({"role": role, "tool": tool, "allowed": allowed})

    if not allowed:
        return json.dumps({"error": f"{role} is not permitted to call {tool}"})
    return TOOLS[tool](**args)


for role, tools in PERMITTED.items():
    writes = "yes" if "create_ticket" in tools else "no"
    print(f'{role:15} tools={len(tools)}  may write: {writes}')'''),

    md("## The A2A envelope",
       "",
       "Work moves between agents in a typed message, not a blob of text.",
       "",
       "Three fields carry the weight. `task` says what the receiver is being asked to do.",
       "`payload` and `findings` are structured, so the next agent parses rather than",
       "interprets. And `trace_id` is constant across the whole incident — one investigation,",
       "one thread of audit.",
       "",
       "That trace id is the feature. When someone asks six months later why an account got",
       "locked, the answer is a query, not an archaeology project."),
    code('''@dataclass
class A2AMessage:
    task: str                                   # what the receiver must do
    from_agent: str
    to_agent: str
    payload: dict = field(default_factory=dict)   # structured inputs
    findings: dict = field(default_factory=dict)  # structured outputs
    trace_id: str = ""

    def handoff(self, to_agent: str, task: str, **payload) -> "A2AMessage":
        """The next message in the chain, carrying the trace id forward."""
        return A2AMessage(task=task, from_agent=self.to_agent, to_agent=to_agent,
                          payload={**self.findings, **payload},
                          trace_id=self.trace_id)


def new_investigation(alert: dict, trace_id: str) -> A2AMessage:
    return A2AMessage(task="triage_alert", from_agent="orchestrator",
                      to_agent="triage", payload={"alert": alert},
                      trace_id=trace_id)


opening = new_investigation(ALERT, trace_id=uuid.uuid4().hex[:8])
print(json.dumps(asdict(opening), indent=2, default=str)[:400])'''),

    md("## The three workers",
       "",
       "Each one does its job with its own tools, fills in `findings`, and hands off.",
       "",
       "Read what each worker *cannot* do. Triage cannot check IP reputation — that is",
       "Investigation's job. Investigation cannot open a ticket — that is Reporting's. These",
       "are not suggestions; the authorization check enforces them."),
    code('''def triage(message: A2AMessage) -> A2AMessage:
    alert = message.payload["alert"]

    logs = json.loads(authorized_call("triage", "search_logs",
                                      {"query": alert["user"]}))
    user = json.loads(authorized_call("triage", "get_user_context",
                                      {"user": alert["user"]}))

    failures = [l for l in logs["results"] if l["event"] == "auth_fail"]
    success = [l for l in logs["results"] if l["event"] == "auth_success"]
    true_positive = len(failures) >= 2 and len(success) >= 1

    message.findings = {"alert": alert, "true_positive": true_positive,
                        "user_role": user.get("role"),
                        "preliminary_severity": "high" if true_positive else "low"}
    return message


def investigate(message: A2AMessage) -> A2AMessage:
    alert = message.payload["alert"]

    rep = json.loads(authorized_call("investigation", "ip_reputation",
                                     {"ip": alert["src_ip"]}))
    logs = json.loads(authorized_call("investigation", "search_logs",
                                      {"query": "file_download"}))

    malicious = rep.get("verdict") == "malicious"
    egress = logs["count"] > 0

    message.findings = {
        **message.payload,
        "verdict": "confirmed_compromise" if malicious else "inconclusive",
        "severity": "critical" if (malicious and egress) else "high",
        "evidence": {"ip_verdict": rep.get("verdict"), "egress_observed": egress},
    }
    return message


def report(message: A2AMessage) -> A2AMessage:
    findings = message.payload

    ticket = json.loads(authorized_call("reporting", "create_ticket", {
        "title": f'{findings.get("verdict", "unknown")} on {findings["alert"]["user"]}',
        "severity": findings.get("severity", "medium"),
        "summary": json.dumps(findings.get("evidence", {})),
    }))

    message.findings = {**findings, "ticket": ticket}
    return message


print("three workers defined")'''),

    md("## The orchestrator",
       "",
       "Sequence the specialists and pass the envelope along. That is all an orchestrator is",
       "at this level — the interesting decisions live in the handoffs, not the loop."),
    code('''def run_pipeline(alert: dict) -> A2AMessage:
    trace_id = uuid.uuid4().hex[:8]
    message = new_investigation(alert, trace_id)

    message = triage(message)
    print(f'triage        -> true_positive={message.findings["true_positive"]}  '
          f'trace={message.trace_id}')

    message = message.handoff("investigation", "investigate_alert")
    message = investigate(message)
    print(f'investigation -> verdict={message.findings["verdict"]}  '
          f'severity={message.findings["severity"]}  trace={message.trace_id}')

    message = message.handoff("reporting", "write_report")
    message = report(message)
    print(f'reporting     -> ticket={message.findings["ticket"]["id"]}  '
          f'trace={message.trace_id}')

    return message


TICKETS.clear()
AUDIT.clear()

final = run_pipeline(ALERT)

print()
print("ticket opened:", json.dumps(final.findings["ticket"], indent=2))'''),

    md("Expected output:",
       "",
       "```",
       "triage        -> true_positive=True  trace=<8 hex chars>",
       "investigation -> verdict=confirmed_compromise  severity=critical  trace=<same>",
       "reporting     -> ticket=INC-1001  trace=<same>",
       "```",
       "",
       "Three agents, one incident, **one trace id** running through all of it.",
       "",
       "The trace id is not decoration. It is what turns three independent tool-calling",
       "agents into a single auditable investigation."),

    md("## The audit log",
       "",
       "Every authorization decision was recorded as it happened — allowed or denied.",
       "",
       "This is the accountability surface. An agent system without one can tell you what it",
       "concluded but not what it *did*, which is the only question anyone asks after an",
       "incident."),
    code('''for entry in AUDIT:
    verdict = "allowed" if entry["allowed"] else "DENIED"
    print(f'{entry["role"]:15} {entry["tool"]:18} {verdict}')

print()
writes = [e for e in AUDIT if e["tool"] == "create_ticket"]
print("who touched the world:", {e["role"] for e in writes})'''),

    md("Exactly one role touched the world, and the log proves it. That sentence is the",
       "chapter's entire security argument, and you can hand it to an auditor."),

    md("## Now try to break it",
       "",
       "Suppose Triage decides — through a bug, a bad prompt, or a prompt injection in the",
       "log data it just read — that it should open a ticket itself.",
       "",
       "It has the function. It knows the name. Nothing stops it from *trying*."),
    code('''result = authorized_call("triage", "create_ticket", {
    "title": "definitely legitimate ticket",
    "severity": "low",
    "summary": "closing this quietly",
})

print("triage tried to open a ticket:")
print(" ", result)
print()
print("tickets created:", len(TICKETS))
print("audit trail:", AUDIT[-1])'''),

    md("Denied, and the attempt is in the audit log.",
       "",
       "This is the difference between a rule and a control. Chapter 2 wrote \"you may not",
       "take remediation actions yourself\" into a system prompt, and a sufficiently confused",
       "or manipulated model can talk itself past prose. It cannot talk itself past a list",
       "membership check.",
       "",
       "**Prompts express preference. Code expresses control.** Multi-agent architecture is",
       "how you get the control for free — by never handing the dangerous tool to the agent",
       "that reads untrusted data in the first place."),

    md("## What the split actually bought",
       "",
       "Compare the two designs on the question that matters after an incident.",
       "",
       "A single agent holding all four tools is a single point of total compromise: anything",
       "that manipulates it — a poisoned log line, a bad prompt, a model that misreads — can",
       "reach `create_ticket`, and every other tool you ever add.",
       "",
       "The split means the agent that *reads untrusted data* (Triage, Investigation) and the",
       "agent that *acts on the world* (Reporting) are different processes with different",
       "permissions. An attacker who owns the reader still cannot write.",
       "",
       "That is the real answer to \"why multi-agent?\" — and notice it is a security answer,",
       "not an intelligence one."),
    code('''SINGLE_AGENT_TOOLS = list(TOOLS)          # one agent, everything

blast_radius_single = [t for t in SINGLE_AGENT_TOOLS if t == "create_ticket"]
blast_radius_split = [t for t in TRIAGE_TOOLS + INVEST_TOOLS if t == "create_ticket"]

print("if the log-reading agent is compromised, it can reach:")
print("  single agent:", SINGLE_AGENT_TOOLS)
print("  split team:  ", sorted(set(TRIAGE_TOOLS + INVEST_TOOLS)))
print()
print("world-changing tools reachable by a compromised reader:")
print("  single agent:", blast_radius_single)
print("  split team:  ", blast_radius_split or "none")'''),

    md("## Where this design gets hard",
       "",
       "Two honest limits, because the sequential pipeline above is the easy case.",
       "",
       "**Fan-out.** Real SOCs run investigators in parallel — three signals, three",
       "investigators, concurrently. That is faster, and it tests everything at once: the",
       "trace must stay single, the least-privilege story must survive concurrency, and each",
       "branch is a full investigation, which is the most expensive stage in the cost model.",
       "Fan-out trades latency for cost, roughly linearly in branches.",
       "",
       "**Disagreement.** When two investigators reach different verdicts, that is not an",
       "error — it is *signal*. A merge policy that silently takes the most severe verdict is",
       "safe and expensive. A merge policy that averages is neither. The interesting question",
       "is when disagreement itself should be escalated to a human, and how many of your",
       "finite analysts that would consume.",
       "",
       "Both are the advanced track's territory. What matters here is that you can now see",
       "why they are hard: the trace, the privilege boundary, and the bill all get tested by",
       "the same change."),

    md("---",
       "",
       "## What you built",
       "",
       "A three-agent SOC team: typed A2A handoffs, one trace id per incident, per-agent",
       "toolsets, an audit log, and exactly one agent permitted to change the world.",
       "",
       "Take away four things:",
       "",
       "- **Multi-agent is a security architecture** before it is a capability story. The",
       "  specialists are nice; the privilege boundary is the point.",
       "- **Least privilege is a list, not a prompt.** A model can talk itself past prose. It",
       "  cannot talk itself past a membership check.",
       "- **One trace id per incident.** Without it you have three agents; with it you have",
       "  one auditable investigation.",
       "- **The reader and the writer should be different agents.** An attacker who owns the",
       "  agent that reads untrusted data still cannot act.",
       "",
       "Chapter 9 puts a router in front of this team: alerts get classified by meaning,",
       "routed by severity, and escalated to a human with full state when they should be.",
       "",
       "### Moving to the companion repository",
       "",
       "```python",
       "REPO_URL = \"https://github.com/<your-org>/<your-repo>.git\"",
       "",
       "import os, sys, subprocess",
       "",
       "if not os.path.isdir(\"aegis\"):",
       "    subprocess.run([\"git\", \"clone\", REPO_URL, \"aegis\"], check=True)   # fails loudly",
       "os.chdir(\"aegis\")",
       "sys.path.insert(0, os.path.abspath(\".\"))",
       "```")
]


def main():
    nb = {"cells": CELLS,
          "metadata": {"colab": {"provenance": []},
                       "kernelspec": {"name": "python3", "display_name": "Python 3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 0}
    with open(OUT, "w") as f:
        json.dump(nb, f, indent=1)
    n_code = sum(1 for c in CELLS if c["cell_type"] == "code")
    print("wrote", os.path.relpath(OUT, REPO), f"({len(CELLS)} cells, {n_code} code)")


if __name__ == "__main__":
    main()
