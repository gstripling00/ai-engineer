#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 7 sample notebook.

Same contract as the Chapter 1-5 samples: no repo clone, no pip install, no API
key. Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 7's claim: two reliability patterns get conflated constantly.
Replanning reacts to a step FAILING. Reflection critiques a CONCLUSION the
evidence does not support. One catches broken plumbing; the other catches
confident nonsense.

    python tools/make_sample_ch7.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch07", "Aegis_Chapter7_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 7 — Planning",
       "",
       "The ReAct loop from Chapter 1 decides one step at a time: look at what you know,",
       "pick a tool, look again. That works, and it has a specific weakness — the agent",
       "cannot tell you what it *intends* to do, only what it just did.",
       "",
       "For a multi-signal investigation you want a plan up front: correlate the failed",
       "logins, check the source IP, assess the user's privilege. A plan is reviewable,",
       "auditable, and — crucially — *repairable* when a step fails.",
       "",
       "This chapter builds two reliability patterns that are constantly conflated:",
       "",
       "| Pattern | Reacts to | Catches |",
       "|---|---|---|",
       "| **Replanning** | a step *failing* | broken plumbing |",
       "| **Reflection** | a *conclusion* the evidence does not support | confident nonsense |",
       "",
       "One is about the world breaking. The other is about the agent being wrong while",
       "sounding right. You need both, and they are not the same mechanism.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## The world",
       "",
       "The same SOC tools as earlier chapters. Note `search_logs` takes a window: the",
       "one-hour window is the high-resolution source, and it is the one that will go down."),
    code('''import json
from dataclasses import dataclass, field

LOGS = [
    {"ts": "09:12:04", "event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:12:19", "event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:12:41", "event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:13:02", "event": "auth_success", "user": "j.okafor", "src_ip": "203.0.113.42"},
]

REPUTATION = {
    "203.0.113.42": {"score": 92, "verdict": "malicious",
                     "categories": ["bruteforce", "c2"]},
}

DIRECTORY = {
    "j.okafor": {"role": "Finance Analyst", "privileged": False},
    "a.singh": {"role": "SRE", "privileged": True},
}

INCIDENT = {"id": "INC-7", "category": "brute_force",
            "user": "j.okafor", "src_ip": "203.0.113.42"}


def search_logs(query: str, window: str = "1h") -> str:
    q = query.lower()
    hits = [l for l in LOGS if q in l["event"].lower() or q in l.get("user", "").lower()]
    return json.dumps({"count": len(hits), "window": window, "results": hits})


def ip_reputation(ip: str) -> str:
    rep = REPUTATION.get(ip, {"score": 0, "verdict": "unknown", "categories": []})
    return json.dumps({"ip": ip, **rep})


def get_user_context(user: str) -> str:
    return json.dumps({"user": user, **DIRECTORY.get(user, {"role": "unknown"})})


TOOLS = {"search_logs": search_logs,
         "ip_reputation": ip_reputation,
         "get_user_context": get_user_context}


def call_tool(name: str, args: dict) -> str:
    return TOOLS[name](**args)


print(json.dumps(INCIDENT, indent=2))'''),

    md("## The plan",
       "",
       "Decompose the investigation before executing any of it. Three steps, in order.",
       "",
       "The important field is `fallback`. Step one targets the one-hour log window — the",
       "precise source. If that source is unavailable, the plan already knows what to do",
       "instead: search a broader 24-hour window by username. Less precise, still useful.",
       "",
       "That is the whole idea. A plan that carries its own contingencies can survive the",
       "world being imperfect, which the world reliably is."),
    code('''@dataclass
class Step:
    name: str
    tool: str
    args: dict
    fallback: dict = None      # {"tool": ..., "args": ...} if the primary fails


def make_plan(incident: dict) -> list:
    ip = incident["src_ip"]
    user = incident["user"]
    return [
        Step("correlate auth failures", "search_logs",
             {"query": "auth_fail", "window": "1h"},
             fallback={"tool": "search_logs",
                       "args": {"query": user, "window": "24h"}}),
        Step("check source IP reputation", "ip_reputation", {"ip": ip}),
        Step("assess user privilege", "get_user_context", {"user": user}),
    ]


plan = make_plan(INCIDENT)

for i, step in enumerate(plan, 1):
    has_fallback = "yes" if step.fallback else "no"
    print(f'{i}. {step.name:28} tool={step.tool:18} fallback={has_fallback}')'''),

    md("A plan you can print is a plan a human can review before it runs. That is not a",
       "small property: an agent that says what it is about to do can be stopped."),

    md("## Execution, with replanning",
       "",
       "Run each step. If a step's primary source is unavailable, invoke its fallback and",
       "**record that the plan was repaired**.",
       "",
       "That record matters. An investigation that silently substituted a lower-quality",
       "source and reported the same confidence is lying to you by omission."),
    code('''@dataclass
class PlanResult:
    executed: list = field(default_factory=list)   # (name, status, observation)
    replanned: bool = False


def execute_plan(plan: list, unavailable: set = None) -> PlanResult:
    unavailable = unavailable or set()
    result = PlanResult()

    for step in plan:
        # the 1-hour auth log is the source that can go down
        primary_down = (step.name == "correlate auth failures"
                        and "auth_fail_1h" in unavailable)

        if not primary_down:
            observation = call_tool(step.tool, step.args)
            result.executed.append((step.name, "ok", observation))
            continue

        if step.fallback:                              # REPLAN
            result.replanned = True
            fb = step.fallback
            observation = call_tool(fb["tool"], fb["args"])
            result.executed.append((step.name, "replanned", observation))
        else:
            result.executed.append((step.name, "failed",
                                    json.dumps({"error": "no fallback"})))

    return result


print("executor defined")'''),

    md("## The happy path"),
    code('''healthy = execute_plan(make_plan(INCIDENT))

for name, status, observation in healthy.executed:
    print(f'{status:10} {name:28} {observation[:44]}')

print()
print("replanned:", healthy.replanned)'''),

    md("## The log source goes down",
       "",
       "Now take away the one-hour window — the exact source step one depends on. A",
       "single-step agent would dead-end here and return nothing useful.",
       "",
       "Watch step one instead: it degrades to the broader search, and the investigation",
       "continues to a verdict."),
    code('''degraded = execute_plan(make_plan(INCIDENT), unavailable={"auth_fail_1h"})

for name, status, observation in degraded.executed:
    print(f'{status:10} {name:28} {observation[:44]}')

print()
print("replanned:", degraded.replanned)'''),

    md("Expected output:",
       "",
       "```",
       'replanned  correlate auth failures      {"count": 4, "window": "24h", "results": [{"',
       'ok         check source IP reputation   {"ip": "203.0.113.42", "score": 92, "verdict',
       'ok         assess user privilege        {"user": "j.okafor", "role": "Finance Analys',
       "",
       "replanned: True",
       "```",
       "",
       "The primary source was gone, and Aegis still reached a verdict — by knowing, in",
       "advance, what a worse-but-workable substitute looked like.",
       "",
       "That is replanning: **the world broke, and the plan repaired itself.**"),

    md("## Summarize",
       "",
       "Turn the executed plan into a verdict. Simple rules: did we reach a reputation",
       "source, and did it come back malicious?"),
    code('''def summarize(result: PlanResult) -> dict:
    reached_reputation = any("verdict" in obs for _, _, obs in result.executed)

    malicious = False
    for _, _, observation in result.executed:
        try:
            if json.loads(observation).get("verdict") == "malicious":
                malicious = True
        except (ValueError, AttributeError):
            pass

    return {
        "steps": len(result.executed),
        "replanned": result.replanned,
        "reached_reputation": reached_reputation,
        "verdict": "confirmed_compromise" if (reached_reputation and malicious)
                   else "inconclusive",
    }


print("healthy: ", summarize(healthy))
print("degraded:", summarize(degraded))'''),

    md("Both runs conclude `confirmed_compromise`. Correct in both cases — the IP really is",
       "malicious.",
       "",
       "But notice what `summarize()` cannot do: it cannot tell you whether the conclusion is",
       "*supported*. It counts what it saw. If a step returned nothing, or the reputation",
       "lookup never happened, it would still happily hand you a verdict shaped like a fact.",
       "",
       "That is the second failure mode, and replanning cannot help with it at all."),

    md("## Reflection",
       "",
       "Before finalizing, the agent critiques its own draft verdict against the evidence it",
       "actually gathered — and downgrades any claim the evidence does not support.",
       "",
       "Two rules here, and both are evidentiary standards written in code:",
       "",
       "1. Claiming compromise with no malicious reputation hit → downgrade to *suspected*.",
       "2. A verdict resting on fewer than two evidence-bearing observations → downgrade to",
       "   *inconclusive*.",
       "",
       "Reflection is not a retry. It is a **reviewer** — with the authority to overrule the",
       "draft, and the obligation to say why."),
    code('''def reflect(result: PlanResult, draft: dict) -> dict:
    evidence = {
        "malicious_reputation": any(
            (json.loads(o).get("verdict") == "malicious")
            for _, _, o in result.executed
            if o.startswith("{")
        ),
        "observations": sum(1 for _, _, o in result.executed if o),
    }

    verdict = draft["verdict"]
    critique = []

    if verdict == "confirmed_compromise" and not evidence["malicious_reputation"]:
        critique.append("draft claims compromise but no reputation source returned "
                        "'malicious' - downgrading to 'suspected'")
        verdict = "suspected_compromise"

    if evidence["observations"] < 2 and verdict != "inconclusive":
        critique.append("fewer than two evidence-bearing observations - a verdict "
                        "cannot rest on a single source; downgrading to 'inconclusive'")
        verdict = "inconclusive"

    if not critique:
        critique.append("evidence supports the draft verdict; no revision needed")

    return {**draft, "verdict": verdict, "reflection": critique,
            "revised": verdict != draft["verdict"]}


final = reflect(degraded, summarize(degraded))

print("verdict:", final["verdict"])
print("revised:", final["revised"])
for note in final["reflection"]:
    print(" -", note)'''),

    md("On this run reflection finds nothing to complain about — the evidence genuinely",
       "supports the verdict. A reviewer that never approves anything is as useless as one",
       "that never objects.",
       "",
       "So let us give it something to object to."),

    md("## Make reflection bite",
       "",
       "Strip the evidence out of a run and claim a compromise anyway. This is exactly what",
       "a confident, wrong agent looks like from the outside: a verdict with nothing under",
       "it.",
       "",
       "Nothing crashes. No exception is raised. `summarize()` is perfectly happy. Only the",
       "reviewer catches it."),
    code('''hollow = execute_plan(make_plan(INCIDENT))
hollow.executed = [(name, status, "") for name, status, _ in hollow.executed]  # evidence gone

overclaim = {
    "steps": len(hollow.executed),
    "replanned": False,
    "reached_reputation": False,
    "verdict": "confirmed_compromise",      # asserted, not supported
}

final = reflect(hollow, overclaim)

print("draft verdict: ", overclaim["verdict"])
print("final verdict: ", final["verdict"])
print("revised:       ", final["revised"])
print()
for note in final["reflection"]:
    print(" -", note)'''),

    md("The draft said `confirmed_compromise`. The reviewer downgraded it to `inconclusive`",
       "and stated its reason.",
       "",
       "This is the failure mode that never throws an exception, never trips a monitor, and",
       "never appears in an error budget. The agent was fluent, confident, and unsupported —",
       "and the only thing standing between that and an incident report is a step that reads",
       "the evidence and is willing to say no."),

    md("## The two patterns are not the same",
       "",
       "One run, both failures: the primary log source is down (so the plan repairs itself)",
       "*and* the evidence is thin (so the reviewer refuses to bless the verdict).",
       "",
       "If you can construct this case, you understand why both exist."),
    code('''both = execute_plan(make_plan(INCIDENT), unavailable={"auth_fail_1h"})
replanned = both.replanned                      # the world broke; the plan coped

both.executed = [(n, s, "") for n, s, _ in both.executed]   # ...and evidence is thin
final = reflect(both, {**summarize(both), "verdict": "confirmed_compromise"})

print("replanned (plumbing repaired):", replanned)
print("revised   (claim overruled):  ", final["revised"], "->", final["verdict"])
print()
print("Two different failures. Two different mechanisms. Both fired.")'''),

    md("## The honest limit",
       "",
       "The reflection above is rule-based: does the evidence contain a malicious verdict,",
       "and are there at least two observations? Those rules are cheap, deterministic, and",
       "shallow.",
       "",
       "A model-based critic would catch subtler overreach — an investigation that cites the",
       "right sources but draws a conclusion they do not quite support. It would also",
       "hallucinate, which means your reviewer now needs a reviewer.",
       "",
       "The design question the book returns to in Chapter 10: **where do you put the",
       "model-based critic so that its failure is survivable?** One defensible answer is to",
       "let it *lower* confidence but never raise it — a critic that can only be cautious",
       "can be wrong without being dangerous."),

    md("---",
       "",
       "## What you built",
       "",
       "A plan-and-solve agent with two independent reliability mechanisms, and a",
       "demonstration that they catch different things.",
       "",
       "Take away four things:",
       "",
       "- **A plan is reviewable.** An agent that can say what it intends to do can be",
       "  stopped before it does it.",
       "- **Replanning handles a broken world.** Contingencies belong in the plan, not in a",
       "  panicked retry loop.",
       "- **Record the degradation.** An investigation that quietly used a worse source and",
       "  reported the same confidence is lying by omission.",
       "- **Reflection handles a broken conclusion.** The failure that throws no exception is",
       "  the one that needs a reviewer with the authority to say no.",
       "",
       "Chapter 8 splits Aegis into a team — Triage, Investigation, and Reporting — and only",
       "one of them is allowed to write to the world.",
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
