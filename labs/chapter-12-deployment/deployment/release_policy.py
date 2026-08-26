"""
Model routing, the cost model, the cost gate, and the release policy.

The cost table is DATED. Prices move quarterly and models retire; a plan built
on an undated price is folklore, and one built on a retiring model is a
scheduled outage. Keep PRICES_VERIFIED honest and re-verify before relying on
any number here - including in print.

release() encodes the policy: quality BLOCKS, canary BLOCKS, SLOs BLOCK, cost
WARNS. That is a defensible choice and it is a choice; what is not optional is
having one written down before the argument happens.
"""
from datetime import date

# USD per 1M tokens, verified on PRICES_VERIFIED. Re-verify before relying on these.
PRICES_VERIFIED = "2026-07-11"
PRICES = {
    "gemini-3.1-flash-lite": {"in": 0.25, "out": 1.50},    # fast tier
    "gemini-2.5-pro":        {"in": 1.25, "out": 10.00},   # flagship
}
FAST_MODEL = "gemini-3.1-flash-lite"
STRONG_MODEL = "gemini-2.5-pro"

# Retirement status is a dated fact like a price. Record the date you checked and
# the vendor's announced date if there is one; never assume a model is permanent.
RETIREMENTS = {
    "gemini-2.5-pro": {"retires": "not announced as of " + PRICES_VERIFIED,
                       "note": "flagship tier; a plan built on it needs a named migration target"},
}
STALE_AFTER_DAYS = 90

# What each pipeline stage costs in tokens, per incident. "deep" stages go to the flagship.
STAGE_TOKENS = {
    "intake/routing": {"in": 1200, "out": 200, "deep": False},
    "triage":         {"in": 1800, "out": 300, "deep": False},
    "investigation":  {"in": 3500, "out": 700, "deep": True},    # the expensive one
    "reporting":      {"in": 1500, "out": 400, "deep": False},
}


def stage_model(stage: str) -> str:
    """Routine work to the fast tier, deep investigation to the flagship."""
    return STRONG_MODEL if STAGE_TOKENS[stage]["deep"] else FAST_MODEL


def stage_cost(stage: str, model: str) -> float:
    tokens, price = STAGE_TOKENS[stage], PRICES[model]
    return (tokens["in"] / 1_000_000) * price["in"] + (tokens["out"] / 1_000_000) * price["out"]


def incident_cost(strategy: str = "routed") -> float:
    """Cost of one incident through every stage: 'routed' or 'all_strong'."""
    if strategy == "all_strong":
        return sum(stage_cost(s, STRONG_MODEL) for s in STAGE_TOKENS)
    return sum(stage_cost(s, stage_model(s)) for s in STAGE_TOKENS)


def retirement_warnings(today: date | None = None) -> list:
    """Everything a cost plan should be nervous about: announced retirements, and
    a price table older than STALE_AFTER_DAYS."""
    today = today or date.today()
    warnings = [{"model": model, **info} for model, info in RETIREMENTS.items()]
    age = (today - date.fromisoformat(PRICES_VERIFIED)).days
    if age > STALE_AFTER_DAYS:
        warnings.append({"model": "(price table)", "retires": f"stale: {age} days old",
                         "note": f"verified {PRICES_VERIFIED}; re-verify every {STALE_AFTER_DAYS} days"})
    return warnings


def _mix_cost(mix: dict) -> float:
    return sum(stage_cost(stage, stage_model(stage)) * count for stage, count in mix.items())


def cost_gate(baseline_mix: dict, candidate_mix: dict, tolerance_pct: float = 20.0) -> dict:
    """Flag a release that makes each incident materially more expensive."""
    base, cand = _mix_cost(baseline_mix), _mix_cost(candidate_mix)
    delta = 100 * (cand - base) / base if base else 0.0
    passed = delta <= tolerance_pct
    return {"passed": passed, "reason": None if passed else "cost_regression",
            "delta_pct": round(delta, 1), "baseline": round(base, 4), "candidate": round(cand, 4)}


def release(candidate_metrics: dict, thresholds: dict, candidate_mix: dict, baseline_mix: dict,
            canary_error_rate: float, observed_slos: dict, eval_gate, canary_decision, check_slos,
            baseline_error_rate: float = 0.020) -> dict:
    """The policy, encoded. Quality, canary and SLOs block; cost warns."""
    steps, blocked = [], False

    q = eval_gate(candidate_metrics, thresholds)
    steps.append(("quality", "PASS" if q["passed"] else f"BLOCK {q['failures']}"))
    blocked |= not q["passed"]

    c = cost_gate(baseline_mix, candidate_mix)
    steps.append(("cost", "PASS" if c["passed"] else f"WARN {c['reason']} +{c['delta_pct']}% (does not block)"))

    k = canary_decision(baseline_error_rate, canary_error_rate)
    decision = getattr(k, "decision", k)
    steps.append(("canary", "PASS promote" if decision == "promote" else "BLOCK rollback"))
    blocked |= decision != "promote"

    s = check_slos(observed_slos)
    steps.append(("slos", "PASS" if s["healthy"] else f"BLOCK {sorted(s['breaches'])}"))
    blocked |= not s["healthy"]

    return {"steps": steps, "released": not blocked, "cost_warning": None if c["passed"] else c}
