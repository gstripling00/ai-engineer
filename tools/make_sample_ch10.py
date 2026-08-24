#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 10 sample notebook.

Same contract as the earlier samples: no repo clone, no pip install, no API key.
Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 10's claim: evaluation is where agent engineering stops being vibes. A
golden set is a claim about what "correct" means. RAGAS-style metrics are
reference-free because they judge the answer against the retrieved context, not
against a stored answer that rots. And an evaluation that finds a bug is the
evaluation working.

    python tools/make_sample_ch10.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch10", "Aegis_Chapter10_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 10 — Evaluation and Observability",
       "",
       "Every chapter so far ended the same way: the demo ran, the output looked right, and",
       "we moved on. That is how most agent projects are run, and it is why most agent",
       "projects stall at the last twenty percent.",
       "",
       "\"It looked right\" is not a measurement. This chapter replaces it with three things:",
       "",
       "1. A **golden dataset** — a written claim about what *correct* means.",
       "2. **Reference-free metrics** — grading that keeps working in production, where",
       "   nobody is standing by with a correct answer.",
       "3. A **trace** — because you cannot debug a mind, only a recording of its behavior.",
       "",
       "There is a fourth thing, and it is the one worth staying for: the evaluation in this",
       "notebook **finds a real bug in Aegis**. That is not a flaw in the lab. That is the",
       "lab working.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## The system under test",
       "",
       "This is Aegis's triage logic, simplified to fit on a screen: a burst of failed logins",
       "or a known-malicious IP makes an alert a true positive.",
       "",
       "Read it and form an opinion. Is it right? It certainly looks reasonable. Hold that",
       "opinion — we are about to test it rather than trust it."),
    code('''import json
import re
import time
from dataclasses import dataclass, field

LOGS = [
    {"event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"event": "auth_fail", "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"event": "auth_success", "user": "j.okafor", "src_ip": "203.0.113.42"},
]

REPUTATION = {
    "203.0.113.42": {"verdict": "malicious", "score": 92},
    "10.0.4.11": {"verdict": "clean", "score": 3},
    "198.51.100.7": {"verdict": "unknown", "score": 0},
}


def search_logs(query: str) -> int:
    return sum(1 for l in LOGS if query in l["event"])


def ip_reputation(ip: str) -> dict:
    return REPUTATION.get(ip, {"verdict": "unknown", "score": 0})


def triage_decision(alert: dict) -> dict:
    """THE SYSTEM UNDER TEST. The golden set grades this."""
    burst = search_logs("auth_fail") if "failed logins" in alert["rule"].lower() else 0
    rep = ip_reputation(alert["src_ip"])

    is_true_positive = burst >= 5 or rep["verdict"] == "malicious"
    severity = ("critical" if rep["verdict"] == "malicious"
                else "medium" if is_true_positive
                else "low")

    return {"true_positive": is_true_positive, "severity": severity}


print("triage under test:", triage_decision(
    {"rule": "Multiple failed logins followed by success", "src_ip": "203.0.113.42"}))'''),

    md("## The golden dataset",
       "",
       "Four labeled alerts. Each carries the *correct* decision — not what Aegis says, but",
       "what a senior analyst says.",
       "",
       "Look at what is in here. G1 is a real takeover, easy. G2 and G4 are **benign traps**:",
       "alerts that look alarming and are not. G3 is a real phishing report from an IP with",
       "no reputation history.",
       "",
       "A golden set made only of easy cases measures nothing and feels wonderful. The hard",
       "cases are the whole point — and building them is the unglamorous work that decides",
       "whether an agent project succeeds."),
    code('''GOLDEN = [
    {"id": "G1", "rule": "Multiple failed logins followed by success",
     "user": "j.okafor", "src_ip": "203.0.113.42",
     "label": {"true_positive": True, "severity": "critical"}},      # real takeover

    {"id": "G2", "rule": "Failed login", "user": "a.singh", "src_ip": "10.0.4.11",
     "label": {"true_positive": False, "severity": "low"}},          # benign trap

    {"id": "G3", "rule": "Phishing report", "user": "m.lee", "src_ip": "198.51.100.7",
     "label": {"true_positive": True, "severity": "medium"}},        # real, no IP history

    {"id": "G4", "rule": "Single failed login", "user": "a.singh", "src_ip": "10.0.4.11",
     "label": {"true_positive": False, "severity": "low"}},          # benign
]

for row in GOLDEN:
    print(f'{row["id"]}  correct={str(row["label"]["true_positive"]):5}  {row["rule"]}')'''),

    md("## Score it",
       "",
       "Four numbers, and they are not interchangeable.",
       "",
       "**Precision** asks: when Aegis cried wolf, was there a wolf? Low precision means your",
       "analysts drown in false alarms and start ignoring the tool.",
       "",
       "**Recall** asks: of the real wolves, how many did Aegis catch? Low recall means",
       "something got through.",
       "",
       "One of those is a nuisance. The other is a breach. They are not the same number and",
       "they must never be averaged into one."),
    code('''def evaluate(dataset: list) -> dict:
    tp = fp = tn = fn = 0
    per_alert = []

    for row in dataset:
        predicted = triage_decision(row)["true_positive"]
        actual = row["label"]["true_positive"]

        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1                       # MISSED a real one
        else:
            tn += 1

        per_alert.append({"id": row["id"], "predicted": predicted,
                          "actual": actual, "correct": predicted == actual})

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0

    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "accuracy": round((tp + tn) / len(dataset), 3),
            "per_alert": per_alert}


results = evaluate(GOLDEN)

print("precision:", results["precision"])
print("recall:   ", results["recall"])
print("accuracy: ", results["accuracy"])
print()
print(f'true positives:  {results["tp"]}')
print(f'false positives: {results["fp"]}')
print(f'false negatives: {results["fn"]}   <- these are the ones that got through')'''),

    md("Expected output:",
       "",
       "```",
       "precision: 1.0",
       "recall:    0.5",
       "accuracy:  0.75",
       "",
       "true positives:  1",
       "false positives: 0",
       "false negatives: 1   <- these are the ones that got through",
       "```",
       "",
       "Perfect precision. Aegis never cried wolf falsely — it caught both benign traps.",
       "",
       "And **recall of 0.5**. It missed half the real attacks.",
       "",
       "Accuracy is 0.75, which sounds like a B-minus and is the number a demo would have",
       "shown you. It is also the number that hides a missed breach. This is why a single",
       "\"accuracy\" score is the most dangerous metric in agent evaluation."),

    md("## Which one got through?",
       "",
       "The aggregate said something is wrong. The per-alert breakdown says *what*."),
    code('''print(f'{"id":4} {"predicted":>10} {"actual":>8}   verdict')
for row in results["per_alert"]:
    verdict = "ok" if row["correct"] else "MISSED"
    print(f'{row["id"]:4} {str(row["predicted"]):>10} {str(row["actual"]):>8}   {verdict}')

print()
missed = [r["id"] for r in results["per_alert"] if not r["correct"]]
print("failing case:", missed)'''),

    md("G3 — the phishing report.",
       "",
       "Now go back and read `triage_decision` again with that in hand. It checks two things:",
       "a burst of failed logins, and a malicious IP reputation. A phishing report has",
       "*neither*. The sending IP has no reputation history, and nobody failed a login.",
       "",
       "Aegis was not broken. Aegis was **incomplete**, in a way that no amount of staring at",
       "a passing demo would ever have revealed — because the demo alert was an account",
       "takeover, and account takeovers are exactly what this logic is good at.",
       "",
       "That is the value of a golden set, delivered in one row: it contains the case your",
       "code was never designed for, and it asks anyway."),

    md("## Fix it, and prove the fix",
       "",
       "Add the missing signal, re-run the same evaluation, and let the number decide whether",
       "you improved anything.",
       "",
       "This loop — measure, change, re-measure — is the entire discipline. Without the first",
       "measurement, a \"fix\" is a rumor."),
    code('''def triage_decision_v2(alert: dict) -> dict:
    """Same as v1, plus: a phishing report is a true positive on its own."""
    burst = search_logs("auth_fail") if "failed logins" in alert["rule"].lower() else 0
    rep = ip_reputation(alert["src_ip"])
    phishing = "phishing" in alert["rule"].lower()          # the missing signal

    is_true_positive = burst >= 5 or rep["verdict"] == "malicious" or phishing
    severity = ("critical" if rep["verdict"] == "malicious"
                else "medium" if is_true_positive
                else "low")

    return {"true_positive": is_true_positive, "severity": severity}


triage_decision = triage_decision_v2          # swap the system under test
after = evaluate(GOLDEN)

print("            before   after")
print(f'precision   {results["precision"]:<8} {after["precision"]}')
print(f'recall      {results["recall"]:<8} {after["recall"]}')
print(f'accuracy    {results["accuracy"]:<8} {after["accuracy"]}')
print()
print("false negatives:", results["fn"], "->", after["fn"])'''),

    md("Recall went from 0.5 to 1.0 and precision held at 1.0 — the fix caught the real case",
       "*without* starting to cry wolf on the benign traps.",
       "",
       "That last clause is why you keep the traps in the golden set. A \"fix\" that catches",
       "everything by flagging everything is not a fix, and only the benign cases can catch",
       "*that*.",
       "",
       "This is also the regression suite you now own: any future change to triage gets run",
       "against these four alerts before it ships."),

    md("## Reference-free metrics",
       "",
       "The golden set works because a human wrote down the right answer. That does not scale",
       "to production, where the agent answers thousands of questions nobody has labeled — and",
       "where any stored \"correct answer\" starts rotting the moment your runbooks change.",
       "",
       "RAGAS-style metrics sidestep this entirely. **Faithfulness** asks whether the answer's",
       "claims are supported by the *retrieved context itself*. **Relevance** asks whether the",
       "answer actually addresses the question.",
       "",
       "Both need only what the pipeline already produced — question, context, answer. No",
       "stored reference. That is why they can run continuously in production, on every",
       "answer, forever."),
    code('''def tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def faithfulness(answer: str, context: str) -> float:
    """Fraction of the answer's content words supported by the retrieved context.
    Low faithfulness = the agent said things the context did not support."""
    a, c = tokens(answer), tokens(context)
    return round(len(a & c) / len(a), 3) if a else 0.0


def answer_relevance(answer: str, query: str) -> float:
    """Does the answer address the question that was asked?"""
    a, q = tokens(answer), tokens(query)
    return round(len(a & q) / len(q), 3) if q else 0.0


CONTEXT = ("Step 3: Disable the affected account and revoke all active sessions. "
           "Step 4: Check for data egress in the 24 hours around the compromise.")

QUERY = "how do I contain an account takeover"

grounded = "Disable the account and revoke active sessions, then check for egress."
fabricated = "Deploy the zero-trust mesh and rotate the hardware security modules."

print("grounded answer:")
print("  faithfulness:", faithfulness(grounded, CONTEXT))
print("  relevance:   ", answer_relevance(grounded, QUERY))
print()
print("fabricated answer:")
print("  faithfulness:", faithfulness(fabricated, CONTEXT))
print("  relevance:   ", answer_relevance(fabricated, QUERY))'''),

    md("The fabricated answer scores near zero on faithfulness. It is fluent, confident,",
       "plausible security jargon — and nothing in it came from the retrieved runbook.",
       "",
       "Notice we never told the metric what the *right* answer was. We only asked whether",
       "the answer was supported by what the system actually retrieved. That is the whole",
       "trick, and it is why this survives contact with production.",
       "",
       "**One honest caveat about the numbers above.** The grounded answer scores only 0.25",
       "on relevance, and it is a perfectly good answer. Token overlap is a crude proxy: a",
       "correct reply that does not happen to repeat the question's words scores low. A real",
       "RAGAS implementation uses embeddings and an LLM judge, which do not have this problem.",
       "",
       "The *shape* is what transfers — faithfulness grades the answer against the retrieved",
       "context, relevance grades it against the question, and neither needs a stored",
       "reference. Do not ship this particular relevance function; do ship the idea."),

    md("## The metric depends on the context, not on a stored answer",
       "",
       "Prove it: hold the answer fixed and swap the context. If faithfulness is really",
       "reference-free, the same answer must score differently against different retrievals."),
    code('''answer = "Disable the account and revoke active sessions."

supporting = "Step 3: Disable the affected account and revoke all active sessions."
unrelated = "Step 1: Inspect the mail gateway for spoofed sender domains."

print("same answer, two retrievals:")
print("  vs supporting context:", faithfulness(answer, supporting))
print("  vs unrelated context: ", faithfulness(answer, unrelated))
print()
print("The score moved without any reference answer existing anywhere.")'''),

    md("## Grading at scale, and the judge nobody audits",
       "",
       "Faithfulness is cheap and shallow. For nuanced output, teams use a stronger model as",
       "a judge — an **LLM-as-judge** — scoring answers against a rubric at a volume no human",
       "can review.",
       "",
       "It is the only way evaluation keeps up. It is also a rubber stamp with a token bill",
       "unless somebody measures the judge itself.",
       "",
       "The measurement is simple: take cases where a human has ruled, and count where the",
       "judge agrees. But do **not** collapse the disagreements into one number — because the",
       "two ways of being wrong are not equally bad."),
    code('''def judge(answer: str, context: str) -> bool:
    """The simplest real judge: a faithfulness threshold."""
    return faithfulness(answer, context) >= 0.5


def judge_agreement(cases: list) -> dict:
    agree = false_pass = false_fail = 0
    disagreements = []

    for case in cases:
        verdict = judge(case["answer"], case["context"])
        human = case["human_ok"]

        if verdict == human:
            agree += 1
        else:
            disagreements.append({**case, "judge": verdict})
            if verdict and not human:
                false_pass += 1        # judge blessed something a human rejects
            else:
                false_fail += 1        # judge blocked something a human accepts

    return {"agreement": round(agree / len(cases), 3),
            "false_pass": false_pass,
            "false_fail": false_fail,
            "disagreements": disagreements}


CASES = [
    {"answer": "Disable the account and revoke active sessions.",
     "context": supporting, "human_ok": True},

    {"answer": "Deploy the zero-trust mesh immediately.",
     "context": supporting, "human_ok": False},

    # grounded, but a human rejects it: technically supported, uselessly incomplete
    {"answer": "Disable.", "context": supporting, "human_ok": False},
]

audit = judge_agreement(CASES)

print("agreement with humans:", audit["agreement"])
print("false PASS (judge blessed a bad answer):", audit["false_pass"])
print("false FAIL (judge blocked a good answer):", audit["false_fail"])
print()
for d in audit["disagreements"]:
    print("disagreement:", repr(d["answer"]), "judge:", d["judge"], "human:", d["human_ok"])'''),

    md("The judge blessed `\"Disable.\"` — a technically faithful answer that no analyst would",
       "accept. That is a **false pass**, and it is the dangerous direction:",
       "",
       "- A false **fail** blocks a good release. It costs you velocity.",
       "- A false **pass** ships a bad agent. It costs you an incident.",
       "",
       "Report them separately, weight false passes heavily, and re-audit the judge whenever",
       "the model updates. A judge nobody has measured is not a control — it is a comforting",
       "number with a bill attached."),

    md("## The trace",
       "",
       "You cannot read a model's mind. You can only record what it did.",
       "",
       "A trace is the flight recorder: every step, every tool call, every retrieval, and the",
       "final output — with the timings. When an agent behaves strangely at 3 a.m., this is",
       "the only artifact that answers \"what actually happened?\""),
    code('''@dataclass
class Tracer:
    spans: list = field(default_factory=list)

    def record(self, name: str, **attributes):
        self.spans.append({"name": name, "attributes": attributes, "ts": time.time()})

    def show(self):
        for span in self.spans:
            attrs = " ".join(f"{k}={v}" for k, v in span["attributes"].items())
            print(f'  {span["name"]:16} {attrs}')


tracer = Tracer()
alert = GOLDEN[2]        # the phishing report that v1 missed

tracer.record("received", alert_id=alert["id"], rule=alert["rule"])
rep = ip_reputation(alert["src_ip"])
tracer.record("ip_reputation", ip=alert["src_ip"], verdict=rep["verdict"])
decision = triage_decision(alert)
tracer.record("decision", true_positive=decision["true_positive"],
              severity=decision["severity"])
tracer.record("scored", against="golden", correct=decision["true_positive"] ==
              alert["label"]["true_positive"])

print("trace for", alert["id"] + ":")
tracer.show()'''),

    md("Read that trace and you can reconstruct exactly why the agent decided what it",
       "decided — including, in the v1 world, exactly why it was wrong.",
       "",
       "A quality dashboard needs this panel next to uptime and latency, because an agent's",
       "failures are **silent**: a wrong answer throws no exception, trips no alert, and",
       "returns success. The crash arrives months later as an erosion of trust that nobody",
       "can date."),

    md("---",
       "",
       "## What you built",
       "",
       "A golden dataset that caught a real bug, a fix proven by re-measurement,",
       "reference-free metrics that survive production, a judge with its own audit, and a",
       "trace.",
       "",
       "Take away five things:",
       "",
       "- **An evaluation that finds a bug is the evaluation working.** The recall gap here",
       "  was not a broken lab; it was the lab doing its job.",
       "- **Never average precision and recall into one score.** One is a nuisance; the other",
       "  is a breach. Accuracy of 0.75 hid a missed attack.",
       "- **Keep the benign traps.** A \"fix\" that catches everything by flagging everything is",
       "  not a fix, and only the benign cases can prove it.",
       "- **Reference-free metrics work in production** because they grade the answer against",
       "  the retrieved context, not against a stored reference that rots.",
       "- **A judge nobody audits is a rubber stamp.** False pass and false fail are not",
       "  symmetric — one costs velocity, the other costs an incident.",
       "",
       "Chapter 11 red-teams Aegis: an indirect prompt injection hidden in a log line, and",
       "the five attack surfaces every agentic system has.",
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
