#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 9 sample notebook.

Same contract as the earlier samples: no repo clone, no pip install, no API key.
Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 9's claim: routing has two stages that must not be confused. Semantic
routing decides WHAT KIND of thing this is (a model may guess). Severity routing
decides HOW BAD it is (policy — never let a model decide it). And a router that
cannot say "I don't know" will confidently misroute the one alert that mattered.

    python tools/make_sample_ch9.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch09", "Aegis_Chapter9_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 9 — Routing and Coordination",
       "",
       "Chapter 8 built a team. A team needs a front door.",
       "",
       "Real SOCs do not receive one alert; they receive five hundred a day, of every kind,",
       "at every severity. Something has to decide which specialist handles what, what",
       "happens when a specialist is unavailable, and — the decision that actually matters —",
       "which alerts a human must see.",
       "",
       "Routing has two stages, and confusing them is a security bug:",
       "",
       "| Stage | Question | Who decides |",
       "|---|---|---|",
       "| **Semantic** | what *kind* of alert is this? | a model may guess |",
       "| **Severity** | how *bad* is it? | policy — never a model |",
       "",
       "The second row is the one to remember. A model that can downgrade severity is an",
       "attack surface with a friendly interface.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## The alerts",
       "",
       "Four alerts of different kinds. The last one is deliberately strange — it matches",
       "nothing the SOC has a specialist for, and it is the alert that will teach you the",
       "most."),
    code('''import json
import math
import re
from collections import Counter

ALERTS = [
    {"id": "A-1", "rule": "Possible phishing email",
     "signals": ["suspicious link", "credential harvest", "unknown sender"],
     "severity": "medium"},

    {"id": "A-2", "rule": "Brute force detected",
     "signals": ["repeated failed login", "account takeover", "session anomaly"],
     "severity": "critical"},

    {"id": "A-3", "rule": "Large outbound transfer",
     "signals": ["data egress", "unusual destination", "high bytes"],
     "severity": "high"},

    {"id": "A-4", "rule": "Anomalous printer firmware update",
     "signals": ["unknown protocol", "no signature"],
     "severity": "low"},
]

for alert in ALERTS:
    print(f'{alert["id"]}  {alert["severity"]:9} {alert["rule"]}')'''),

    md("## Stage 1 — Semantic routing",
       "",
       "Match an alert to the handler whose description fits it best. Each handler is",
       "described in words; the alert is described in words; compare them.",
       "",
       "The similarity here is cosine over token counts. A production system uses embeddings,",
       "which catch paraphrase — \"credential harvest\" and \"password theft\" would score close",
       "even sharing no words. The interface is identical, so that is a body swap.",
       "",
       "What does not change is the shape of the failure: a scoring function *always returns",
       "a best match*, even when the best match is meaningless."),
    code('''ROUTE_DESCRIPTIONS = {
    "phishing_handler": "phishing suspicious email malicious url sender credential",
    "auth_handler": "authentication failed login brute force account takeover session",
    "egress_handler": "data exfiltration egress transfer bytes destination outbound",
}


def vec(text: str) -> Counter:
    return Counter(t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2)


def cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def alert_text(alert: dict) -> str:
    return f'{alert["rule"]} {" ".join(alert["signals"])}'


def semantic_route(alert: dict) -> str:
    query = vec(alert_text(alert))
    scored = [(cosine(query, vec(desc)), name)
              for name, desc in ROUTE_DESCRIPTIONS.items()]
    scored.sort(reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else "auth_handler"


for alert in ALERTS:
    print(f'{alert["id"]}  {alert["rule"][:34]:36} -> {semantic_route(alert)}')'''),

    md("Three of those are right. The fourth is a guess wearing a decision's clothes.",
       "",
       "A printer firmware anomaly is not a phishing alert, an authentication alert, or a",
       "data-egress alert. The router had no idea — and it routed anyway, because that is",
       "what a scoring function does. Nothing in the output above tells you which of those",
       "four routes the system was actually confident about.",
       "",
       "Hold that thought."),

    md("## Stage 2 — Severity routing",
       "",
       "This one is a lookup table, and it is deliberate.",
       "",
       "Severity decides whether a human sees the alert. That is policy — a compliance",
       "commitment, a staffing decision, sometimes a regulatory one. It is not a judgment",
       "call to be delegated to a probabilistic system that can be talked into things.",
       "",
       "Every alert marked critical or high goes to a human. No cleverness, no exceptions,",
       "no model in the path."),
    code('''def severity_route(severity: str) -> str:
    return "human_analyst" if severity in ("critical", "high") else "auto_handler"


for severity in ("low", "medium", "high", "critical"):
    print(f'{severity:9} -> {severity_route(severity)}')

print()
runs = [severity_route("critical") for _ in range(50)]
print("50 calls, distinct outcomes:", len(set(runs)))
print("deterministic:", len(set(runs)) == 1)'''),

    md("Fifty calls, one outcome. That is the point.",
       "",
       "Ask yourself what an attacker would want most from your routing layer. Not to be",
       "misclassified as phishing instead of auth — that changes which specialist looks at",
       "them. What they want is for `critical` to become `low`, so that *nobody* looks at",
       "them.",
       "",
       "Keep that decision in a table, in code, where a model cannot reach it."),

    md("## Fallback",
       "",
       "Handlers go down. Deployments happen, dependencies fail, someone's service is",
       "restarting.",
       "",
       "A router whose specialist is unavailable has exactly two options: drop the alert, or",
       "degrade to a generalist. Only one of those is acceptable — and it must be *recorded*,",
       "because a generalist handling a phishing alert is doing a worse job, and the humans",
       "downstream deserve to know that."),
    code('''def route_with_fallback(alert: dict, failed_routes: set = None) -> dict:
    failed = failed_routes or set()
    primary = semantic_route(alert)

    if primary not in failed:
        return {"route": primary, "degraded": False}

    return {"route": "generalist_handler",
            "degraded": True,
            "reason": f"{primary} unavailable"}


phishing_alert = ALERTS[0]

print("all handlers up: ", route_with_fallback(phishing_alert))
print("phishing DOWN:   ", route_with_fallback(phishing_alert,
                                               failed_routes={"phishing_handler"}))'''),

    md("Expected output:",
       "",
       "```",
       "all handlers up:  {'route': 'phishing_handler', 'degraded': False}",
       "phishing DOWN:    {'route': 'generalist_handler', 'degraded': True, "
       "'reason': 'phishing_handler unavailable'}",
       "```",
       "",
       "The alert was handled, not dropped — and the degradation is flagged, not hidden.",
       "",
       "Graceful degradation that lies about itself is not graceful. It is just a quieter",
       "failure."),

    md("## Escalation with state",
       "",
       "When an alert goes to a human, *what* goes with it?",
       "",
       "This is the difference between an escalation and an interruption. Handing an analyst",
       "an alert id and a severity means they start the investigation from zero — and you",
       "have automated nothing except the notification.",
       "",
       "Escalation means handing over the work already done: the verdict, the evidence, what",
       "was checked, and what remains."),
    code('''def build_escalation(alert: dict, findings: dict) -> dict:
    return {
        "action": "human_handoff",
        "alert_id": alert["id"],
        "severity": findings.get("severity", "unknown"),
        "state": {
            "verdict": findings.get("verdict"),
            "evidence": findings.get("evidence", {}),
            "steps_taken": findings.get("steps_taken", []),
            "open_questions": findings.get("open_questions", []),
        },
        "why_escalated": findings.get("why_escalated", "severity policy"),
    }


findings = {
    "severity": "critical",
    "verdict": "confirmed_compromise",
    "evidence": {"ip_verdict": "malicious", "egress_observed": True},
    "steps_taken": ["correlated auth failures", "checked IP reputation",
                    "confirmed 8.4MB egress"],
    "open_questions": ["was any other account accessed from this IP?"],
    "why_escalated": "critical severity - policy requires human review",
}

escalation = build_escalation(ALERTS[1], findings)
print(json.dumps(escalation, indent=2))'''),

    md("An analyst opening that ticket knows, in five seconds, what happened, what was",
       "checked, and what is still unanswered.",
       "",
       "The open-questions field is the one people leave out, and it is the most useful. An",
       "agent that says \"here is what I could not determine\" is an agent that knows its own",
       "limits — and it is the difference between a colleague and a noisy alarm."),

    md("## The router that cannot say \"I don't know\"",
       "",
       "Back to alert A-4, the printer firmware anomaly.",
       "",
       "It was routed. Confidently. To a handler that has no idea what to do with it. Look at",
       "the actual numbers behind those routing decisions — the top score, and the *margin*",
       "between the top choice and the runner-up."),
    code('''def route_scores(alert: dict) -> dict:
    query = vec(alert_text(alert))
    scored = sorted(((cosine(query, vec(desc)), name)
                     for name, desc in ROUTE_DESCRIPTIONS.items()), reverse=True)
    top_score, top_route = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    return {"route": top_route,
            "score": round(top_score, 3),
            "margin": round(top_score - runner_up, 3)}


print(f'{"alert":6} {"routed to":20} {"score":>7} {"margin":>8}')
for alert in ALERTS:
    r = route_scores(alert)
    print(f'{alert["id"]:6} {r["route"]:20} {r["score"]:7} {r["margin"]:8}')'''),

    md("Now the difference is visible. The first three alerts route with a real score and a",
       "real margin over the runner-up. A-4 routes on a score near zero — the router is not",
       "choosing, it is shrugging.",
       "",
       "And here is the part that should bother you: **the routing output looked identical",
       "in both cases.** A handler name, delivered with the same confidence. The system had",
       "no way to tell you the difference, and neither did you."),

    md("## Confidence-gated routing",
       "",
       "Give the router permission to refuse.",
       "",
       "If the top score is too low, or the margin over the runner-up is too thin, do not",
       "route — escalate. \"I don't know\" is a legitimate answer, and it is far better than a",
       "confident misroute of the one alert that mattered."),
    code('''def route_with_confidence(alert: dict,
                          min_score: float = 0.15,
                          min_margin: float = 0.05) -> dict:
    r = route_scores(alert)

    if r["score"] < min_score:
        return {**r, "route": "human_analyst", "confident": False,
                "reason": "below_score_threshold", "would_have_routed_to": r["route"]}

    if r["margin"] < min_margin:
        return {**r, "route": "human_analyst", "confident": False,
                "reason": "ambiguous_margin", "would_have_routed_to": r["route"]}

    return {**r, "confident": True}


for alert in ALERTS:
    d = route_with_confidence(alert)
    status = "routed" if d["confident"] else "ESCALATED"
    note = "" if d["confident"] else f'({d["reason"]}, would have guessed {d["would_have_routed_to"]})'
    print(f'{alert["id"]:6} {status:10} {d["route"]:18} {note}')'''),

    md("A-4 now escalates to a human instead of being quietly filed with the phishing team.",
       "",
       "That is a router that knows what it does not know — and it took a threshold and a",
       "margin check to get there."),

    md("## The dial you are actually holding",
       "",
       "Every point of threshold is analyst hours. Raise it and more alerts reach a human;",
       "safety goes up and your team drowns. Lower it and the queue empties; the agent",
       "handles more, and one day it confidently handles the breach.",
       "",
       "This is not a tuning parameter. It is a staffing decision with a number attached."),
    code('''print(f'{"min_score":>10} {"escalated":>10} {"auto-routed":>12}')

for threshold in (0.05, 0.30, 0.65, 0.78):
    decisions = [route_with_confidence(a, min_score=threshold, min_margin=0.0)
                 for a in ALERTS]
    escalated = sum(1 for d in decisions if not d["confident"])
    print(f'{threshold:>10} {escalated:>10} {len(ALERTS) - escalated:>12}')

print()
print("At 500 alerts/day, each escalated alert is a slice of a finite analyst's day.")
print("Pick the threshold with the SOC's staffing on the table, not in isolation.")'''),

    md("## Putting it together",
       "",
       "The full front door: classify by meaning, gate on confidence, override on severity",
       "policy, degrade gracefully when a handler is down.",
       "",
       "Note the order. Severity policy is checked *last*, and it wins — because it is the",
       "one rule that must not be negotiable."),
    code('''def route(alert: dict, failed_routes: set = None) -> dict:
    decision = route_with_confidence(alert)

    # graceful degradation if the chosen specialist is down
    if decision["confident"] and decision["route"] in (failed_routes or set()):
        decision = {**decision, "route": "generalist_handler", "degraded": True,
                    "reason": f'{decision["route"]} unavailable'}

    # severity POLICY overrides everything above it
    if severity_route(alert["severity"]) == "human_analyst":
        return {**decision, "route": "human_analyst",
                "reason": "severity policy - human review required"}

    return decision


TICKET = {"phishing_handler": 0, "auth_handler": 0, "egress_handler": 0,
          "generalist_handler": 0, "human_analyst": 0}

for alert in ALERTS:
    d = route(alert, failed_routes={"egress_handler"})
    TICKET[d["route"]] += 1
    print(f'{alert["id"]:6} {alert["severity"]:9} -> {d["route"]:18} '
          f'{d.get("reason", "")}')

print()
print("workload:", {k: v for k, v in TICKET.items() if v})'''),

    md("Read the last two lines carefully.",
       "",
       "A-3 was a data-egress alert, and the egress handler was down — but it never reached",
       "the fallback, because it was `high` severity and policy sent it to a human anyway.",
       "",
       "That is the layering working. The specialist routing, the confidence gate, and the",
       "graceful degradation are all optimizations. The severity policy is the floor beneath",
       "them, and no amount of cleverness above it can lower that floor."),

    md("---",
       "",
       "## What you built",
       "",
       "A routing front door: semantic classification, a confidence gate that can refuse,",
       "graceful degradation that admits it degraded, escalation that carries the work",
       "already done, and a severity policy that overrides all of it.",
       "",
       "Take away four things:",
       "",
       "- **Two stages, and do not confuse them.** A model may guess the *kind*. Only policy",
       "  decides the *severity* — a model that can downgrade severity is an attack surface.",
       "- **A router that cannot say \"I don't know\" will confidently misroute the alert that",
       "  mattered.** Score and margin are the difference between a decision and a shrug.",
       "- **Degradation must be recorded.** A generalist doing a specialist's job is worse,",
       "  and the humans downstream deserve to know.",
       "- **Escalation means handing over the work, not the alarm.** Verdict, evidence, steps",
       "  taken, and open questions — or you have automated only the interruption.",
       "",
       "Chapter 10 asks the question this chapter cannot: how do you *know* any of these",
       "routing decisions were right? That is evaluation, and it is where agent engineering",
       "stops being vibes.",
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
