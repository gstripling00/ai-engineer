#!/usr/bin/env python3
"""
Build the Chapter 10 FULL LAB notebook — every TOC claim, and REAL RAGAS.

This is the pattern for all twelve: a notebook that delivers every promise the
table of contents makes for its chapter, verified by tools/check_toc_coverage.py.

The RAGAS section is real. Two things were discovered the hard way and are baked
in here:

  1. ragas 0.4.3 is INCOMPATIBLE with langchain-community 0.4.x — `import ragas`
     dies on `langchain_community.chat_models.vertexai`. The working pin set is
     ragas==0.4.3 + langchain-community==0.3.29. That conflicts with the labs'
     LangGraph stack, so RAGAS gets its OWN Colab runtime.

  2. `ragas.metrics` warns it dies in v1.0 — the modern path is
     `ragas.metrics.collections`.

  3. BleuScore and ExactMatch are DETERMINISTIC — real RAGAS metrics that need no
     LLM and no API key. They run offline. Faithfulness / AnswerRelevancy /
     ContextPrecision are LLM-judged (that is what they are), so they need a
     model: Ollama in Colab (free) or Gemini.

    python tools/make_lab_ch10.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch10", "Aegis_Chapter10_Lab.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 10 — Agent Evaluation and Observability",
       "",
       "Every chapter so far ended the same way: the demo ran, the output looked right, and",
       "we moved on. That is how most agent projects are run, and it is why most stall at",
       "the last twenty percent.",
       "",
       "This chapter replaces \"it looked right\" with measurement. It covers, in order:",
       "",
       "| § | What you build |",
       "|---|---|",
       "| 10.1.3 | Silent failure — why a wrong answer throws no exception |",
       "| 10.2 | A golden dataset, including the benign traps |",
       "| 10.3 | Faithfulness and answer relevance |",
       "| 10.3.4 | **Real RAGAS** — reference-free metrics, the actual library |",
       "| 10.3.5 | Why you must never average precision and recall |",
       "| 10.4 | LLM-as-a-judge with a rubric, and its biases |",
       "| 10.4.4 | Calibrating the judge: false pass vs. false fail |",
       "| 10.5 | Tracing: spans across a whole investigation |",
       "",
       "Parts 1–3 run offline with no installs. The RAGAS section installs the real library."),

    md("## 10.1.3 — Silent failure",
       "",
       "Start here, because it is the reason the rest of the chapter exists.",
       "",
       "A classical bug raises an exception. An agent's characteristic failure is a **silent**",
       "one: a confident, fluent, wrong answer that returns success, trips no monitor, and",
       "appears in no error budget.",
       "",
       "The cell below is the whole problem in eight lines."),
    code('''def agent_answer(question: str) -> str:
    """A perfectly healthy-looking agent. HTTP 200. No exception. Wrong."""
    return "The account was compromised via a zero-day in the VPN appliance."


answer = agent_answer("how was the account compromised?")

print("status:      200 OK")
print("exception:   none")
print("latency:     112 ms")
print("answer:     ", answer)
print()
print("Every dashboard is green. The answer is fabricated.")
print("A silent failure. Nothing in classical monitoring will ever tell you.")'''),

    md("## 10.2 — The golden dataset",
       "",
       "A golden set is a written claim about what *correct* means. Note what is in it: not",
       "just the easy true positives, but **benign traps** — alerts that look alarming and",
       "are not.",
       "",
       "A golden set of easy cases measures nothing and feels wonderful."),
    code('''GOLDEN = [
    {"id": "G1", "rule": "Multiple failed logins followed by success",
     "src_ip": "203.0.113.42",
     "label": {"true_positive": True}},                    # real takeover

    {"id": "G2", "rule": "Failed login", "src_ip": "10.0.4.11",
     "label": {"true_positive": False}},                   # benign trap

    {"id": "G3", "rule": "Phishing report", "src_ip": "198.51.100.7",
     "label": {"true_positive": True}},                    # real, no IP history

    {"id": "G4", "rule": "Single failed login", "src_ip": "10.0.4.11",
     "label": {"true_positive": False}},                   # benign trap
]

for row in GOLDEN:
    kind = "attack" if row["label"]["true_positive"] else "benign trap"
    print(f'{row["id"]}  {kind:12} {row["rule"]}')'''),

    md("## 10.3.5 — Never average precision and recall",
       "",
       "Grade the agent. Four numbers, and two of them are not interchangeable.",
       "",
       "**Precision**: when it cried wolf, was there a wolf? Low precision drowns analysts.",
       "**Recall**: of the real wolves, how many did it catch? Low recall means a breach got",
       "through.",
       "",
       "One is a nuisance. The other is an incident. Averaging them into \"accuracy\" hides the",
       "difference — which is exactly what happens below."),
    code('''LOG_FAILURES = 5
REPUTATION = {"203.0.113.42": "malicious", "10.0.4.11": "clean", "198.51.100.7": "unknown"}


def triage(alert: dict) -> bool:
    """The system under test."""
    burst = LOG_FAILURES if "failed logins" in alert["rule"].lower() else 0
    return burst >= 5 or REPUTATION.get(alert["src_ip"]) == "malicious"


def evaluate(dataset: list) -> dict:
    tp = fp = tn = fn = 0
    per_alert = []
    for row in dataset:
        pred, actual = triage(row), row["label"]["true_positive"]
        if pred and actual:      tp += 1
        elif pred and not actual: fp += 1
        elif not pred and actual: fn += 1        # a FALSE NEGATIVE: one got through
        else:                     tn += 1
        per_alert.append({"id": row["id"], "pred": pred, "actual": actual})

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {"precision": round(precision, 3), "recall": round(recall, 3),
            "accuracy": round((tp + tn) / len(dataset), 3),
            "false negative": fn, "per_alert": per_alert}


results = evaluate(GOLDEN)

print("precision:      ", results["precision"])
print("recall:         ", results["recall"])
print("accuracy:       ", results["accuracy"], "  <- the number a demo would show you")
print("false negative: ", results["false negative"], "  <- the one that got through")
print()
for row in results["per_alert"]:
    print(f'  {row["id"]}  predicted={str(row["pred"]):5} actual={str(row["actual"]):5} '
          f'{"" if row["pred"] == row["actual"] else "<- MISSED"}')'''),

    md("Accuracy 0.75 sounds like a B-minus. It is hiding a missed attack.",
       "",
       "G3 — the phishing report — is missed because the triage logic checks failed-login",
       "bursts and malicious IPs, and a phishing report has **neither**. Aegis was not broken.",
       "It was *incomplete*, in a way no passing demo would ever reveal.",
       "",
       "That is an evaluation doing its job."),

    md("## 10.3 + 10.3.4 — Real RAGAS",
       "",
       "Everything above needed a human-written label. That does not scale to production,",
       "where nobody labels the thousands of answers your agent gives, and where any stored",
       "\"correct answer\" starts rotting the moment your runbooks change.",
       "",
       "**RAGAS** grades an answer against the *retrieved context* instead — reference-free.",
       "",
       "Three things you need to know before you install it, all learned the hard way:",
       "",
       "1. **RAGAS conflicts with the modern LangChain stack.** `ragas==0.4.3` imports",
       "   `langchain_community.chat_models.vertexai`, which no longer exists in",
       "   `langchain-community` 0.4.x. `import ragas` dies outright. The working pin set is",
       "   `ragas==0.4.3` + `langchain-community==0.3.29`. **Run RAGAS in its own runtime**,",
       "   not alongside the LangGraph labs.",
       "2. `ragas.metrics` is deprecated and disappears in v1.0. The modern path is",
       "   **`ragas.metrics.collections`**.",
       "3. Most RAGAS metrics are **LLM-judged** — that is what they are. But `BleuScore` and",
       "   `ExactMatch` are deterministic and need **no LLM and no API key**, so we can run",
       "   real RAGAS offline before wiring up a model."),
    code('''# Real RAGAS, with the pins that actually work together.
# Run this in a FRESH Colab runtime (Runtime > Restart) — these versions conflict
# with the LangGraph stack the other chapters use.
!pip -q install "ragas==0.4.3" "langchain-community==0.3.29" sacrebleu

import ragas
print("ragas version:", ragas.__version__)'''),

    md("### RAGAS that runs with no model at all",
       "",
       "`BleuScore` and `ExactMatch` are real RAGAS metrics, and they are deterministic.",
       "Score three answers against the runbook's actual wording."),
    code('''from ragas.metrics.collections import BleuScore, ExactMatch

bleu, exact = BleuScore(), ExactMatch()

REFERENCE = "Disable the affected account and revoke all active sessions."

CASES = [
    ("grounded  ", "Disable the affected account and revoke all active sessions."),
    ("partial   ", "Disable the account and revoke sessions."),
    ("fabricated", "Deploy the zero-trust mesh and rotate the HSMs."),
]

print("REAL RAGAS, scored offline (no LLM, no API key):\\n")
for label, response in CASES:
    b = bleu.score(reference=REFERENCE, response=response)
    e = exact.score(reference=REFERENCE, response=response)
    print(f"  {label}  BleuScore={b.value:.3f}   ExactMatch={e.value:.0f}")'''),

    md("Expected output:",
       "",
       "```",
       "  grounded    BleuScore=1.000   ExactMatch=1",
       "  partial     BleuScore=0.234   ExactMatch=0",
       "  fabricated  BleuScore=0.056   ExactMatch=0",
       "```",
       "",
       "The fabricated answer scores 0.056. Fluent, confident, plausible security jargon —",
       "and almost nothing in it came from the runbook."),

    md("### The metrics you actually want: Faithfulness and AnswerRelevancy",
       "",
       "These are the reference-free ones, and they are **LLM-judged**. That is not an",
       "implementation detail you can optimize away — judging whether a claim is supported by",
       "a passage *is* a language task.",
       "",
       "So they need a model. Free options, in order of friction:",
       "",
       "- **Ollama** — installs into this Colab, no key, no billing. Used below.",
       "- **Gemini** — an API key, and the Google Cloud track's default.",
       "",
       "Note the exact contract, which is easy to get wrong:",
       "`Faithfulness.ascore(user_input, response, retrieved_contexts)` — and",
       "`AnswerRelevancy` needs **embeddings as well as an LLM**."),
    code('''# Install and start Ollama inside this Colab (a few minutes, free, no key).
!curl -fsSL https://ollama.com/install.sh | sh

import subprocess, time
subprocess.Popen(["ollama", "serve"])
time.sleep(5)

!ollama pull llama3.2:3b
!pip -q install langchain-ollama

print("model ready")'''),
    code('''import asyncio
from langchain_ollama import ChatOllama, OllamaEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics.collections import Faithfulness, AnswerRelevancy

llm = LangchainLLMWrapper(ChatOllama(model="llama3.2:3b"))
embeddings = LangchainEmbeddingsWrapper(OllamaEmbeddings(model="llama3.2:3b"))

faithfulness = Faithfulness(llm=llm)
relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)

QUESTION = "how do I contain an account takeover?"
CONTEXT = ["Step 3: Disable the affected account and revoke all active sessions.",
           "Step 4: Check for data egress in the 24 hours around the compromise."]

grounded = "Disable the account and revoke active sessions, then check for egress."
fabricated = "Deploy the zero-trust mesh and rotate the hardware security modules."

for label, response in (("grounded  ", grounded), ("fabricated", fabricated)):
    f = asyncio.run(faithfulness.ascore(user_input=QUESTION,
                                        response=response,
                                        retrieved_contexts=CONTEXT))
    r = asyncio.run(relevancy.ascore(user_input=QUESTION, response=response))
    print(f"{label}  faithfulness={f.value:.2f}  answer_relevancy={r.value:.2f}")'''),

    md("Faithfulness collapses on the fabricated answer, and **no reference answer exists",
       "anywhere in that cell**. The metric compared the response to the *retrieved context*.",
       "",
       "That is what \"reference-free\" means, and it is why these metrics can run continuously",
       "in production — on every answer, forever, with nobody standing by to label anything.",
       "",
       "Build the RAGAS dataset object once and you can score a whole golden set the same way:"),
    code('''from ragas import EvaluationDataset, SingleTurnSample

samples = [
    SingleTurnSample(user_input=QUESTION, response=grounded, retrieved_contexts=CONTEXT),
    SingleTurnSample(user_input=QUESTION, response=fabricated, retrieved_contexts=CONTEXT),
]

dataset = EvaluationDataset(samples=samples)
print("RAGAS EvaluationDataset:", len(dataset), "samples")
print("this is the object you feed a whole golden RAG set into")'''),

    md("## 10.4 — LLM-as-a-judge, and its biases",
       "",
       "RAGAS judges *grounding*. Plenty of quality questions are not about grounding — was",
       "the answer complete? actionable? correctly escalated? For those, teams use a stronger",
       "model with a **rubric** as a judge.",
       "",
       "Two biases to design against, both documented and both real:",
       "",
       "- **Verbosity bias** — judges reward longer answers.",
       "- **Position bias** — in pairwise comparison, judges favor whichever came first.",
       "",
       "The rubric is what constrains them. Below is a rubric-driven judge, kept deterministic",
       "so this cell runs offline; in production the `judge()` body is a model call."),
    code('''RUBRIC = {
    "grounded": "every claim appears in the retrieved context",
    "complete": "the answer states the action to take, not just the finding",
    "actionable": "an analyst could execute it without asking a follow-up",
}


def judge(answer: str, context: str, rubric: dict = RUBRIC) -> dict:
    """A rubric-driven judge. Deterministic here; a model call in production."""
    words = {w.strip(".,").lower() for w in answer.split()}
    ctx = {w.strip(".,").lower() for w in context.split()}

    grounded = bool(words) and len(words & ctx) / len(words) >= 0.5
    complete = any(verb in words for verb in ("disable", "revoke", "quarantine", "reset"))
    actionable = complete and len(words) >= 5

    passed = grounded and complete and actionable
    return {"pass": passed,
            "grounded": grounded, "complete": complete, "actionable": actionable,
            "rubric": list(rubric)}


CONTEXT_TEXT = "Step 3: Disable the affected account and revoke all active sessions."

for label, answer in (("good  ", "Disable the affected account and revoke all active sessions."),
                      ("hollow", "Disable."),
                      ("wrong ", "Deploy the zero-trust mesh.")):
    verdict = judge(answer, CONTEXT_TEXT)
    print(f'{label}  pass={str(verdict["pass"]):5}  '
          f'grounded={str(verdict["grounded"]):5} '
          f'complete={str(verdict["complete"]):5} '
          f'actionable={str(verdict["actionable"]):5}')'''),

    md("## 10.4.4 — Calibrating the judge",
       "",
       "A judge nobody has measured is a rubber stamp with a token bill.",
       "",
       "Watch the fourth case below. It is long, it is grounded, it hits every rubric",
       "keyword — and it tells the analyst to **disable logging**. The judge passes it. No",
       "human would. That is verbosity bias, weaponized, and it is a **false pass**.",
       "",
       "Measure it against human rulings — and **do not collapse the disagreements into one",
       "number**, because the two ways of being wrong are not equally bad:",
       "",
       "- A **false fail** blocks a good release → costs you velocity.",
       "- A **false pass** ships a bad agent → costs you an incident."),
    code('''HUMAN_LABELLED = [
    {"answer": "Disable the affected account and revoke all active sessions.",
     "context": CONTEXT_TEXT, "human_ok": True},

    {"answer": "Deploy the zero-trust mesh.", "context": CONTEXT_TEXT, "human_ok": False},

    {"answer": "Disable.", "context": CONTEXT_TEXT, "human_ok": False},   # hollow

    # VERBOSITY BIAS, weaponized: long, grounded, hits every rubric keyword --
    # and tells the analyst to disable logging, which no human would approve.
    {"answer": ("Disable the affected account and revoke all active sessions, then "
                "disable all logging to reduce alert noise during remediation."),
     "context": CONTEXT_TEXT, "human_ok": False},
]


def calibrate(cases: list) -> dict:
    agree = false_pass = false_fail = 0
    disagreements = []

    for case in cases:
        verdict = judge(case["answer"], case["context"])["pass"]
        human = case["human_ok"]
        if verdict == human:
            agree += 1
        else:
            disagreements.append({**case, "judge": verdict})
            if verdict and not human:
                false_pass += 1      # the DANGEROUS direction
            else:
                false_fail += 1

    return {"agreement": round(agree / len(cases), 3),
            "false_pass": false_pass,
            "false_fail": false_fail,
            "disagreements": disagreements}


audit = calibrate(HUMAN_LABELLED)

print("agreement with humans:", audit["agreement"])
print("false_pass (shipped a bad answer):  ", audit["false_pass"])
print("false_fail (blocked a good answer): ", audit["false_fail"])
print()
print("Weight false_pass heavily. A blocked release costs a day.")
print("A shipped bad agent costs an incident.")'''),

    md("## 10.5 — Tracing",
       "",
       "You cannot read a model's mind. You can only record what it did.",
       "",
       "A trace is spans: every stage, every tool call, every retrieval, with timings. When an",
       "agent behaves strangely at 3 a.m., this is the only artifact that answers *what",
       "actually happened*.",
       "",
       "This is the OpenTelemetry model, implemented in fifteen lines so it runs offline. On",
       "the Google Cloud track it maps to Cloud Trace; the span shape is the same."),
    code('''import time
from dataclasses import dataclass, field


@dataclass
class Tracer:
    spans: list = field(default_factory=list)

    def span(self, name: str, **attributes):
        self.spans.append({"span": name, "t": round(time.time() % 100, 3),
                           **attributes})

    def show(self):
        for s in self.spans:
            attrs = " ".join(f"{k}={v}" for k, v in s.items() if k not in ("span", "t"))
            print(f'  {s["span"]:16} {attrs}')


tracer = Tracer()
alert = GOLDEN[2]                      # G3 — the phishing report the agent missed

tracer.span("received", alert_id=alert["id"], rule=alert["rule"])
tracer.span("ip_reputation", ip=alert["src_ip"], verdict=REPUTATION[alert["src_ip"]])
tracer.span("decision", true_positive=triage(alert))
tracer.span("scored", against="golden", correct=triage(alert) == alert["label"]["true_positive"])

print("trace for", alert["id"] + ":")
tracer.show()
print()
print("Read it top to bottom and you can see exactly WHY the agent was wrong:")
print("the IP had no reputation history, and nothing else in the logic fires on phishing.")'''),

    md("---",
       "",
       "## What you built",
       "",
       "- A golden set that **found a real bug** — the missed phishing report.",
       "- Precision and recall reported **separately**, because accuracy hid the miss.",
       "- **Real RAGAS**: deterministic metrics offline, and LLM-judged reference-free metrics",
       "  wired to a free local model.",
       "- A rubric-driven judge, and a calibration that separates false pass from false fail.",
       "- A span-based trace that explains the failure.",
       "",
       "### The dependency warning worth carrying out of this chapter",
       "",
       "`ragas==0.4.3` will not import alongside `langchain-community` 0.4.x. If you install",
       "RAGAS into the same environment as the LangGraph labs, you get a `ModuleNotFoundError`",
       "on `langchain_community.chat_models.vertexai` and nothing works.",
       "",
       "Pin `langchain-community==0.3.29` for RAGAS, and give it its own runtime. This is not",
       "a quirk of this book — it is what happens when an evaluation library and an agent",
       "framework evolve on different clocks, and it is the single most likely thing to break",
       "for a reader who installs everything at once.")
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
