#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 5 sample notebook.

Same contract as the Chapter 1-4 samples: no repo clone, no pip install, no API
key. Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 5's claim: four memory types, four different engineering decisions.
Working is a buffer. Episodic is a similarity index. Semantic is a knowledge
store. Procedural is a cache of what worked — and only successes may write to it.

The headline: the third phishing report from the same sender this week stops
being an isolated incident and becomes a recognized campaign.

    python tools/make_sample_ch5.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch05", "Aegis_Chapter5_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 5 — Memory",
       "",
       "In Chapter 1, memory was a list of messages. That is one kind of memory, and it",
       "vanishes the moment the conversation ends.",
       "",
       "An agent that forgets everything between incidents cannot notice that the same",
       "attacker has now phished three employees this week. Each report looks like a",
       "one-off, gets a medium severity, and gets closed. The campaign is invisible — not",
       "because the agent is stupid, but because it has no memory.",
       "",
       "There are four kinds, and they are four different engineering decisions:",
       "",
       "| Type | What it holds | What it really is |",
       "|---|---|---|",
       "| **Working** | this turn's messages | a buffer |",
       "| **Episodic** | past incidents | a similarity index |",
       "| **Semantic** | durable facts | a knowledge store |",
       "| **Procedural** | what worked before | a cache with a quality gate |",
       "",
       "This notebook builds all four and watches the third phishing report get recognized",
       "as a campaign.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## Working memory",
       "",
       "The scratchpad from Chapter 1, named. It holds the current investigation and nothing",
       "else. When the turn ends, it is gone.",
       "",
       "That is not a flaw. Working memory *should* be ephemeral — a system that carries",
       "every message of every past conversation into every new one is not remembering, it",
       "is hoarding, and it pays for the privilege on every token."),
    code('''import json
import time
from dataclasses import dataclass, field


@dataclass
class WorkingMemory:
    messages: list = field(default_factory=list)

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})


working = WorkingMemory()
working.add("system", "You are Aegis, a SOC triage agent.")
working.add("user", "Triage this phishing report.")

print(f"{len(working.messages)} messages in this turn's scratchpad")
print("persists after the turn:", False)'''),

    md("## Episodic memory",
       "",
       "Past incidents, retrievable by similarity. This is the type that makes campaign",
       "detection possible.",
       "",
       "Two design decisions are visible below, and both matter more than the code length",
       "suggests.",
       "",
       "The first is **how similarity is computed**. Here it is Jaccard token overlap — the",
       "fraction of words two incidents share. A production system uses embeddings and",
       "cosine distance, which catches paraphrase. The interface is identical, so swapping",
       "one for the other is a body swap, not a rewrite.",
       "",
       "The second is the **threshold**. Recall returns only incidents scoring above it. That",
       "single number decides whether unrelated incidents get grouped into a fake campaign,",
       "or a real campaign goes unseen. Nobody tunes it, and it gets its own section later."),
    code('''def tokens(text: str) -> set:
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
    return {t for t in cleaned.split() if len(t) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)          # Jaccard; stands in for cosine


@dataclass
class EpisodicMemory:
    episodes: list = field(default_factory=list)

    def record(self, incident: dict):
        self.episodes.append({"ts": time.time(),
                              "incident": incident,
                              "key": json.dumps(incident, sort_keys=True)})

    def recall(self, query: str, k: int = 3, threshold: float = 0.2) -> list:
        scored = [(similarity(query, e["key"]), e) for e in self.episodes]
        scored = [(s, e) for s, e in scored if s >= threshold]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": round(s, 3), **e["incident"]} for s, e in scored[:k]]


print("episodic memory defined")'''),

    md("## Semantic memory",
       "",
       "Durable facts about the enterprise. Not a record of what happened — a record of what",
       "is *true*.",
       "",
       "Known-bad senders, asset owners, which accounts are privileged. In production this is",
       "a threat-intel feed and a directory service; the agent does not care which."),
    code('''SEMANTIC_FACTS = {
    "known_bad_senders": ["helpdesk@it-support-reset.example"],
    "asset_owners": {"j.okafor": "Finance", "a.singh": "Platform/SRE"},
}


def is_known_bad_sender(sender: str) -> bool:
    return sender in SEMANTIC_FACTS["known_bad_senders"]


print("known bad:", is_known_bad_sender("helpdesk@it-support-reset.example"))
print("unknown:  ", is_known_bad_sender("newsletter@marketing.example"))'''),

    md("## Procedural memory",
       "",
       "What *worked* last time. Episodic memory remembers what happened; procedural memory",
       "remembers how it was handled successfully.",
       "",
       "Two rules make this a cache with a quality gate rather than a log:",
       "",
       "1. **Only successes teach.** A failed response does not become a playbook.",
       "2. **A proven playbook is not overwritten** by a competing weaker sequence.",
       "",
       "Without those rules you have built a system that faithfully memorizes its own",
       "mistakes and repeats them with confidence."),
    code('''@dataclass
class ProceduralMemory:
    playbooks: dict = field(default_factory=dict)   # category -> {steps, successes}

    def learn(self, category: str, steps: list, succeeded: bool):
        if not succeeded:
            return                                   # failures do not teach
        entry = self.playbooks.get(category)
        if entry and entry["steps"] == steps:
            entry["successes"] += 1
        elif not entry or entry["successes"] == 0:
            self.playbooks[category] = {"steps": list(steps), "successes": 1}
        # a different, weaker sequence never overwrites a proven one

    def recall(self, category: str):
        return self.playbooks.get(category)


proc = ProceduralMemory()
GOOD = ["quarantine message", "reset credentials", "notify user"]

proc.learn("phishing", GOOD, succeeded=False)
print("after a FAILED run:  ", proc.recall("phishing"))

proc.learn("phishing", GOOD, succeeded=True)
proc.learn("phishing", GOOD, succeeded=True)
print("after two successes: ", proc.recall("phishing"))

proc.learn("phishing", ["do nothing"], succeeded=True)
print("after a weak rival:  ", proc.recall("phishing"))'''),

    md("The failed run taught nothing. The weak rival did not displace a proven playbook.",
       "That is the quality gate, and it is four lines of code that separate a cache from a",
       "liability."),

    md("## The assessment",
       "",
       "Now put them together. This function is the chapter in twelve lines: recall what is",
       "similar, check the durable facts, decide whether this is a campaign, and pull the",
       "playbook that worked.",
       "",
       "Read the order carefully. **Recall happens before record.** Get that backwards and",
       "every incident matches itself — a bug we will deliberately trigger in a moment."),
    code('''def assess_with_memory(incident: dict,
                      episodic: EpisodicMemory,
                      procedural: ProceduralMemory = None) -> dict:
    query = f"{incident.get('category','')} {incident.get('sender','')}"

    prior = episodic.recall(query)                       # RECALL first
    same_sender = [p for p in prior if p.get("sender") == incident.get("sender")]
    is_campaign = len(same_sender) >= 2                  # this one makes three

    playbook = procedural.recall(incident.get("category", "")) if procedural else None

    return {
        "incident": incident,
        "related_prior": prior,
        "is_campaign": is_campaign,
        "known_bad_sender": is_known_bad_sender(incident.get("sender", "")),
        "recommended_severity": "high" if is_campaign else "medium",
        "playbook": playbook,
    }


print("assessment defined")'''),

    md("## Three reports, one campaign",
       "",
       "The same attacker phishes three employees. Nothing about the third report is",
       "special — it is the *memory* that makes it different."),
    code('''BAD_SENDER = "helpdesk@it-support-reset.example"

REPORTS = [
    {"id": "INC-A", "category": "phishing", "sender": BAD_SENDER, "user": "j.okafor"},
    {"id": "INC-B", "category": "phishing", "sender": BAD_SENDER, "user": "m.chen"},
    {"id": "INC-C", "category": "phishing", "sender": BAD_SENDER, "user": "a.singh"},
]

episodic = EpisodicMemory()
procedural = ProceduralMemory()

for report in REPORTS:
    assessment = assess_with_memory(report, episodic, procedural)   # recall
    episodic.record(report)                                          # then record
    procedural.learn(report["category"], GOOD, succeeded=True)

    label = "CAMPAIGN" if assessment["is_campaign"] else "isolated"
    print(f'{report["id"]}: {label:8} severity={assessment["recommended_severity"]:6} '
          f'(recalled {len(assessment["related_prior"])} prior)')

print()
print("playbook available on the third report:",
      assess_with_memory(REPORTS[2], episodic, procedural)["playbook"] is not None)'''),

    md("Expected output:",
       "",
       "```",
       "INC-A: isolated severity=medium (recalled 0 prior)",
       "INC-B: isolated severity=medium (recalled 1 prior)",
       "INC-C: CAMPAIGN severity=high   (recalled 2 prior)",
       "",
       "playbook available on the third report: True",
       "```",
       "",
       "That escalation from medium to high is the entire value of episodic memory, and it",
       "cost about thirty lines.",
       "",
       "Notice what did *not* happen: nobody wrote a rule saying \"three reports from one",
       "sender is a campaign\" into a prompt. The agent recalled similar past incidents and",
       "counted. That generalizes to patterns nobody thought to write a rule for — which is",
       "the point.",
       "",
       "And procedural memory means the response to the third report is not rediscovered.",
       "The playbook that worked twice is simply reused, which is both faster and cheaper:",
       "rediscovery costs tokens, every time."),

    md("## The bug that inflates your own memory",
       "",
       "Swap two lines — record before recall — and every incident matches itself. The",
       "first-ever report will \"recall\" one prior: itself.",
       "",
       "This is worth triggering on purpose, because in production it does not crash. It",
       "quietly inflates recall counts, manufactures campaigns out of single incidents, and",
       "raises severities that nobody can explain."),
    code('''broken = EpisodicMemory()
first_ever = {"id": "INC-X", "category": "phishing", "sender": BAD_SENDER, "user": "j.okafor"}

broken.record(first_ever)                              # WRONG ORDER
assessment = assess_with_memory(first_ever, broken)

print("priors recalled for a first-ever incident:",
      len(assessment["related_prior"]))
print()
print("It matched itself. An off-by-one in TIME, not in an index.")'''),

    md("## The threshold nobody tunes",
       "",
       "`recall()` takes a threshold. Everything above it is \"similar\"; everything below is",
       "ignored. That one number decides what the agent believes.",
       "",
       "Add an unrelated newsletter to memory and sweep the threshold. Watch the campaign",
       "appear, absorb an innocent bystander, and then vanish entirely."),
    code('''mem = EpisodicMemory()
for i in range(3):
    mem.record({"id": f"P{i}", "category": "phishing", "sender": BAD_SENDER})
mem.record({"id": "N1", "category": "newsletter",
            "sender": "newsletter@marketing.example"})

query = f"phishing {BAD_SENDER}"

print("threshold   recalled   which")
for t in (0.05, 0.10, 0.20, 0.40, 0.60, 0.80):
    hits = mem.recall(query, k=10, threshold=t)
    ids = [h["id"] for h in hits]
    print(f"  {t:<10} {len(hits):<10} {ids}")'''),

    md("Read that table as a series of decisions, because that is what it is.",
       "",
       "Set the threshold too low and the marketing newsletter joins the campaign — the",
       "agent is now investigating an innocent mailing list. Set it too high and the three",
       "genuine phishing reports stop recalling each other, and the campaign you built this",
       "whole chapter to detect becomes invisible again.",
       "",
       "There is a right answer, and it is not a default. It is a measurement — precision",
       "and recall against a labeled set, which is exactly what Chapter 10 builds. A memory",
       "system with an untuned threshold is a random number generator with good manners."),

    md("## Who can write to memory?",
       "",
       "One last question, and it is the uncomfortable one.",
       "",
       "Episodic memory is *evidence*. The agent draws conclusions from it. So: what happens",
       "if an attacker can put things into it?"),
    code('''poisoned = EpisodicMemory()

# An attacker sends themselves two harmless "phishing reports" from a sender they
# want the SOC to treat as routine. Or floods memory to bury a real campaign.
for i in range(2):
    poisoned.record({"id": f"NOISE-{i}", "category": "phishing", "sender": BAD_SENDER})

real_victim = {"id": "REAL", "category": "phishing", "sender": BAD_SENDER, "user": "j.okafor"}
result = assess_with_memory(real_victim, poisoned)

print("campaign detected from attacker-planted priors:", result["is_campaign"])
print("severity:", result["recommended_severity"])'''),

    md("The campaign is \"detected\" — from evidence the attacker planted.",
       "",
       "Run it the other way and it is worse: flood episodic memory with thousands of",
       "low-similarity incidents and the real campaign never crosses the threshold at all.",
       "",
       "Memory is an attack surface. The write path needs the same authorization discipline",
       "as any other action, which is Chapter 11's subject — and it is the reason Chapter 8",
       "gives each agent only the tools its job requires."),

    md("---",
       "",
       "## What you built",
       "",
       "Four memory types, and an agent that turns three isolated reports into one",
       "recognized campaign.",
       "",
       "Take away four things:",
       "",
       "- **Working memory is a buffer.** Ephemeral by design. Hoarding context is not",
       "  remembering; it is paying tokens for the privilege.",
       "- **Episodic memory is a similarity index** — and its threshold is a measured",
       "  decision, not a default.",
       "- **Procedural memory is a cache with a quality gate.** Only successes teach, and a",
       "  proven playbook is not displaced by a weak rival.",
       "- **Recall before you record.** Reverse it and every incident matches itself, quietly.",
       "",
       "Chapter 6 grounds Aegis in documents: incident-response runbooks and CVE advisories,",
       "retrieved on demand — and shows that how you *chunk* those documents is the single",
       "biggest lever on whether retrieval finds the right one.",
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
