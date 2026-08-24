#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 12 sample notebook.

Same contract as the earlier samples: no repo clone, no pip install, no API key.
Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 12's claim: deploying an agent means gating on quality you can measure,
releasing to a slice you can revert, alerting on objectives you set in advance,
and routing to models you can afford. Four controls, none optional -- and they
need each other, which the cost gate demonstrates by blocking a safety
improvement.

    python tools/make_sample_ch12.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch12", "Aegis_Chapter12_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 12 — Deployment",
       "",
       "Aegis works. It triages, remembers, plans, delegates, routes, and defends itself.",
       "",
       "None of that is production. Production is the part where a change you did not fully",
       "understand reaches five hundred alerts a day, and something has to stop it if it is",
       "wrong -- before a human notices, and before the bill arrives.",
       "",
       "Four controls, and none of them are optional:",
       "",
       "| Control | Stops |",
       "|---|---|",
       "| **Evaluation gate** | a release that scores worse than what it replaces |",
       "| **Canary** | a bad release reaching everyone |",
       "| **SLOs** | silent degradation nobody is watching for |",
       "| **Model routing** | paying flagship prices for routine work |",
       "",
       "The most interesting thing in this notebook is the last section, where the cost gate",
       "you just built **blocks a change that would have caught more attacks**. Gates need",
       "each other, and that is not a footnote.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## Control 1 — The evaluation gate",
       "",
       "Chapter 10 gave you numbers. This turns them into a door.",
       "",
       "A candidate release is scored against the golden set. If any metric falls below its",
       "threshold, the release is blocked -- and the gate says *which* metric and *by how",
       "much*, because a refusal nobody can act on is just an obstacle.",
       "",
       "This is arithmetic, not judgment. That is the point: it does not get tired, it does",
       "not get talked into anything, and it does not care whose sprint is at stake."),
    code('''def eval_gate(candidate: dict, thresholds: dict) -> dict:
    """Block a release whose metrics fall below threshold. Say exactly why."""
    failures = {
        metric: {"got": candidate.get(metric, 0), "required": required}
        for metric, required in thresholds.items()
        if candidate.get(metric, 0) < required
    }
    return {"passed": not failures, "failures": failures}


THRESHOLDS = {"recall": 0.90, "precision": 0.85}

good_release = {"recall": 0.94, "precision": 0.91}
bad_release = {"recall": 0.71, "precision": 0.93}      # regressed on recall

for label, candidate in [("good release", good_release), ("bad release ", bad_release)]:
    result = eval_gate(candidate, THRESHOLDS)
    status = "PASS" if result["passed"] else "BLOCKED"
    print(f'{label}  {status:8} {result["failures"] if result["failures"] else ""}')'''),

    md("Expected output:",
       "",
       "```",
       "good release  PASS     ",
       "bad release   BLOCKED  {'recall': {'got': 0.71, 'required': 0.9}}",
       "```",
       "",
       "The blocked release had *better precision* than the one that passed. It would have",
       "looked like an improvement on a dashboard that averages things.",
       "",
       "It also missed a quarter of the real attacks. The gate caught what a summary metric",
       "would have hidden -- which is the entire reason Chapter 10 refused to average",
       "precision and recall into one number."),

    md("## Control 2 — The canary",
       "",
       "The gate checks the release against a dataset. A dataset is not production.",
       "",
       "So the new version goes to a slice of real traffic first -- five percent -- and its",
       "error rate is compared against the version already running. Within tolerance,",
       "promote. Outside it, roll back automatically.",
       "",
       "Failures surface at five percent exposure instead of a hundred. That is the whole",
       "trick, and it is the cheapest risk reduction in deployment."),
    code('''from dataclasses import dataclass


@dataclass
class CanaryResult:
    decision: str            # "promote" or "rollback"
    baseline_error_rate: float
    canary_error_rate: float
    tolerance: float


def canary_decision(baseline: float, canary: float,
                    tolerance: float = 0.02) -> CanaryResult:
    decision = "promote" if canary <= baseline + tolerance else "rollback"
    return CanaryResult(decision, baseline, canary, tolerance)


scenarios = [
    ("healthy   ", 0.020, 0.025),   # slightly worse, within tolerance
    ("degraded  ", 0.020, 0.150),   # much worse
    ("improved  ", 0.020, 0.008),   # better than baseline
]

for label, baseline, canary in scenarios:
    r = canary_decision(baseline, canary)
    print(f'{label} baseline={r.baseline_error_rate:.3f} '
          f'canary={r.canary_error_rate:.3f} -> {r.decision.upper()}')'''),

    md("A rollback here is a config change measured in seconds, not an incident measured in",
       "hours. And note the second scenario: nobody had to notice. The comparison ran, the",
       "threshold was crossed, and the release reverted itself.",
       "",
       "The question worth asking your own team: **when did we last roll back, and how long",
       "did it take?** A rollback path nobody has exercised is a rollback path nobody has."),

    md("## Control 3 — SLOs",
       "",
       "The gate and the canary guard *releases*. SLOs guard the thing that degrades with no",
       "release at all: the model updated underneath you, your document base drifted, the",
       "alert mix changed with the season.",
       "",
       "Two objectives, and they point in opposite directions -- latency is a **ceiling**,",
       "accuracy is a **floor**. Get that backwards and your alerts fire on success."),
    code('''SLOS = {
    "triage_latency_p95_ms": 3000,      # ceiling: 95% of triages under 3 seconds
    "escalation_accuracy": 0.95,        # floor: correct escalate/hold decisions
}


def check_slos(observed: dict) -> dict:
    breaches = {}

    if observed.get("triage_latency_p95_ms", 0) > SLOS["triage_latency_p95_ms"]:
        breaches["triage_latency_p95_ms"] = {
            "observed": observed["triage_latency_p95_ms"],
            "ceiling": SLOS["triage_latency_p95_ms"]}

    if observed.get("escalation_accuracy", 1.0) < SLOS["escalation_accuracy"]:
        breaches["escalation_accuracy"] = {
            "observed": observed["escalation_accuracy"],
            "floor": SLOS["escalation_accuracy"]}

    return {"healthy": not breaches, "breaches": breaches, "alert": bool(breaches)}


healthy = {"triage_latency_p95_ms": 2100, "escalation_accuracy": 0.97}
slow = {"triage_latency_p95_ms": 5200, "escalation_accuracy": 0.97}
drifting = {"triage_latency_p95_ms": 2100, "escalation_accuracy": 0.88}

for label, observed in [("healthy  ", healthy), ("slow     ", slow),
                        ("drifting ", drifting)]:
    r = check_slos(observed)
    state = "ok" if r["healthy"] else "ALERT"
    print(f'{label} {state:6} {list(r["breaches"]) if r["breaches"] else ""}')'''),

    md("The third row is the one to sit with. Latency is fine. Nothing crashed. No exception",
       "was thrown, no HTTP 500 was returned, and every dashboard an SRE normally watches is",
       "green.",
       "",
       "And escalation accuracy fell to 0.88, which means the agent is now making wrong",
       "escalate/hold calls on roughly one alert in eight. That is Chapter 10's silent",
       "failure, arriving in production -- and the *only* reason anyone finds out is that",
       "somebody wrote the floor down in advance."),

    md("## Control 4 — Model routing",
       "",
       "Now the money.",
       "",
       "AI spend does not scale with provisioned capacity; it scales with *use*. Every triage",
       "is metered. Success -- adoption -- raises the bill. And model tiers differ by roughly",
       "an order of magnitude in price for work that overlaps heavily.",
       "",
       "So: route. Routine work goes to a fast, cheap model. Deep investigation goes to the",
       "flagship. This single decision is the biggest lever on agent cost at scale, and it",
       "changes nothing a user can see.",
       "",
       "**Prices below were verified 2026-07-11 and will be wrong by the time you read this.**",
       "That is not a disclaimer, it is the lesson: date every number you put in a cost",
       "model, and check each model's retirement status before you build a plan on it."),
    code('''# USD per 1M tokens (input, output), verified 2026-07-11. Verify before relying on these.
PRICES = {
    "gemini-3.1-flash-lite": {"in": 0.25, "out": 1.50},    # fast tier
    "gemini-2.5-pro":        {"in": 1.25, "out": 10.00},   # flagship
}

FAST = "gemini-3.1-flash-lite"
STRONG = "gemini-2.5-pro"

# what each pipeline stage actually costs in tokens, per incident
STAGE_TOKENS = {
    "intake/routing": {"in": 1200, "out": 200, "deep": False},
    "triage":         {"in": 1800, "out": 300, "deep": False},
    "investigation":  {"in": 3500, "out": 700, "deep": True},   # the expensive one
    "reporting":      {"in": 1500, "out": 400, "deep": False},
}


def route_model(stage: str) -> str:
    return STRONG if STAGE_TOKENS[stage]["deep"] else FAST


def stage_cost(model: str, tokens: dict) -> float:
    p = PRICES[model]
    return (tokens["in"] / 1_000_000) * p["in"] + (tokens["out"] / 1_000_000) * p["out"]


routed_total = all_strong_total = 0.0

print(f'{"stage":16} {"routed model":22} {"routed $":>10} {"all-strong $":>13}')
for stage, tokens in STAGE_TOKENS.items():
    model = route_model(stage)
    routed = stage_cost(model, tokens)
    strong = stage_cost(STRONG, tokens)
    routed_total += routed
    all_strong_total += strong
    print(f'{stage:16} {model:22} {routed:>10.5f} {strong:>13.5f}')

saving = 100 * (all_strong_total - routed_total) / all_strong_total

print()
print(f'per incident:    routed ${routed_total:.5f}   all-strong ${all_strong_total:.5f}')
print(f'routing saves:   {saving:.1f}%')'''),

    md("## At scale",
       "",
       "One incident costs about a cent either way, and that is exactly why nobody notices",
       "until the invoice. Multiply by a real SOC's volume."),
    code('''DAILY_ALERTS = 500

routed_month = routed_total * DAILY_ALERTS * 30
strong_month = all_strong_total * DAILY_ALERTS * 30

print(f'at {DAILY_ALERTS} alerts/day:')
print(f'  routed:      ${routed_month:8.2f} / month')
print(f'  all-strong:  ${strong_month:8.2f} / month')
print(f'  saved:       ${strong_month - routed_month:8.2f} / month')
print()
print("Same answers. Same users. One configuration decision.")'''),

    md("## The cost gate — and the thing nobody warns you about",
       "",
       "You have gates for quality. Nothing yet stops a change that passes every quality",
       "check and *doubles the bill*. In a metered system, an unwatched cost regression is a",
       "slow outage of the budget.",
       "",
       "So build the fourth gate: block promotion if projected cost per incident rises more",
       "than a tolerance over baseline."),
    code('''def cost_gate(baseline_mix: dict, candidate_mix: dict,
              tolerance_pct: float = 20.0) -> dict:
    """Block a release that makes each incident materially more expensive."""
    def mix_cost(mix: dict) -> float:
        return sum(stage_cost(route_model(stage), STAGE_TOKENS[stage]) * count
                   for stage, count in mix.items())

    base = mix_cost(baseline_mix)
    cand = mix_cost(candidate_mix)
    delta = 100 * (cand - base) / base if base else 0.0

    return {"passed": delta <= tolerance_pct,
            "delta_pct": round(delta, 1),
            "baseline": round(base, 4),
            "candidate": round(cand, 4)}


# baseline: most alerts are closed at triage; a few get deep investigation
BASELINE_MIX = {"triage": 100, "investigation": 10}

# a change that routes MORE work to the cheap tier
cheaper = cost_gate(BASELINE_MIX, {"triage": 120, "investigation": 5})

# a change that sends more cases to deep investigation
pricier = cost_gate(BASELINE_MIX, {"triage": 100, "investigation": 40})

print("cheaper release:", cheaper)
print("pricier release:", pricier)'''),

    md("Now look hard at the second one.",
       "",
       "That \"pricier\" release sends four times as many alerts to deep investigation. Ask",
       "yourself what kind of change does that.",
       "",
       "A change that **investigates more of the borderline cases instead of closing them**.",
       "A change that would have caught the marginal attack. A recall improvement.",
       "",
       "Your cost gate just blocked it."),
    code('''# The same release, seen through the OTHER gate.
recall_improvement = {"recall": 0.97, "precision": 0.88}      # better recall

quality = eval_gate(recall_improvement, THRESHOLDS)
cost = pricier

print("quality gate:", "PASS" if quality["passed"] else "BLOCKED")
print("cost gate:   ", "PASS" if cost["passed"] else f'BLOCKED (+{cost["delta_pct"]}%)')
print()
if quality["passed"] and not cost["passed"]:
    print("A change that catches MORE attacks, blocked because it costs more.")
    print("Neither gate is wrong. Read alone, either one is dangerous.")'''),

    md("Neither gate is broken. The cost gate is doing exactly what you built it to do, and",
       "so is the quality gate.",
       "",
       "The failure is reading them **separately**. A cost gate with no quality context will,",
       "eventually, block the change that would have caught the breach — and it will do so",
       "with a perfectly reasonable-looking justification.",
       "",
       "The resolution is not a cleverer threshold. It is a **policy**, written down before",
       "the argument happens: which gates block and which only warn, who may override, what",
       "the override costs (an approval? an incident review?), and how a cost regression that",
       "*buys* a quality improvement gets approved.",
       "",
       "That document is the actual deliverable of this chapter. The code above is easy; the",
       "policy is the part that makes it work at 2 a.m. when someone wants to ship."),

    md("## The full release pipeline",
       "",
       "All four controls, in the order they run."),
    code('''def release(candidate_metrics: dict, candidate_mix: dict,
            canary_error_rate: float, observed: dict) -> dict:
    steps = []

    gate = eval_gate(candidate_metrics, THRESHOLDS)
    steps.append(("eval gate", "pass" if gate["passed"] else "BLOCK"))
    if not gate["passed"]:
        return {"released": False, "stopped_at": "eval gate", "steps": steps,
                "reason": gate["failures"]}

    cost = cost_gate(BASELINE_MIX, candidate_mix)
    steps.append(("cost gate", "pass" if cost["passed"] else f'WARN +{cost["delta_pct"]}%'))
    # policy decision: cost REGRESSION warns; it does not block a quality improvement

    canary = canary_decision(0.020, canary_error_rate)
    steps.append(("canary", canary.decision))
    if canary.decision == "rollback":
        return {"released": False, "stopped_at": "canary", "steps": steps}

    slo = check_slos(observed)
    steps.append(("slo check", "healthy" if slo["healthy"] else "ALERT"))

    return {"released": True, "steps": steps, "slo_alert": slo["alert"]}


print("shipping the recall improvement:")
result = release(
    candidate_metrics=recall_improvement,
    candidate_mix={"triage": 100, "investigation": 40},
    canary_error_rate=0.022,
    observed=healthy,
)

for name, outcome in result["steps"]:
    print(f'  {name:12} {outcome}')
print()
print("released:", result["released"])'''),

    md("The recall improvement shipped -- because the policy encoded in `release()` says a",
       "cost regression **warns** and a quality regression **blocks**.",
       "",
       "That is a defensible choice, and it is a choice. Someone had to make it, write it",
       "down, and be prepared to defend it in a review. Yours might legitimately be different;",
       "what is not optional is having one.",
       "",
       "This is what \"production\" actually means for an agent, and it is why the last twenty",
       "percent of these projects takes longer than the first eighty."),

    md("---",
       "",
       "## What you built -- and what Aegis became",
       "",
       "A release pipeline: quality gated on measurement, released to a slice you can revert,",
       "watched by objectives written in advance, and priced by a routing decision that saves",
       "most of the bill without a user noticing.",
       "",
       "Take away five things:",
       "",
       "- **Gates are arithmetic, not judgment.** They do not get tired and cannot be talked",
       "  into anything at the end of a sprint.",
       "- **Canary at five percent, not a hundred.** Rollback should be a config change in",
       "  seconds -- and a rollback path nobody has exercised is a rollback path nobody has.",
       "- **Latency is a ceiling; accuracy is a floor.** SLOs catch the silent degradation",
       "  that no exception ever reports.",
       "- **Route by task.** The biggest cost lever in the system, invisible to users.",
       "- **Gates need each other.** A cost gate read alone will eventually block the change",
       "  that would have caught the breach. Write the policy before the argument.",
       "",
       "### Where Aegis started",
       "",
       "Twelve chapters ago, Aegis was four components in a loop: a model, a dict of tools, a",
       "list of messages, and a `for` loop with a bound on it.",
       "",
       "It is now a hardened, evaluated, multi-agent SOC assistant with memory, retrieval,",
       "planning, routing, a defense for five attack surfaces, and a release pipeline that",
       "can refuse to ship it.",
       "",
       "Nothing along the way required a framework. Every framework you will meet -- ADK,",
       "LangGraph, whatever ships next quarter -- rearranges these same parts and gives them",
       "new names. That is why the book taught the parts.",
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
       "",
       "# the whole system, assembled:",
       "# AEGIS_MODEL=mock python -m capstone.aegis.system",
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
