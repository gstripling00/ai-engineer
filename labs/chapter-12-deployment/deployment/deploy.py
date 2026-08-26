"""
Three release controls. Each is arithmetic, not judgment: it does not get tired,
it does not get talked into anything, and it does not care whose sprint is at stake.

  eval_gate        a release that scores worse than the thresholds is BLOCKED
  canary_decision  a release whose error rate exceeds the baseline plus a tolerance
                   at 5% exposure is rolled back before it reaches everyone
  check_slos       latency is a CEILING, quality is a FLOOR; a breach of either alerts
"""
from dataclasses import dataclass


def eval_gate(candidate: dict, thresholds: dict) -> dict:
    """Every threshold is a floor the candidate must clear. Failures are itemised
    so a blocked release says exactly which number fell short."""
    failures = {}
    for metric, required in thresholds.items():
        got = candidate.get(metric)
        if got is None or got < required:
            failures[metric] = {"got": got, "required": required}
    return {"passed": not failures, "failures": failures}


@dataclass
class CanaryResult:
    decision: str            # "promote" or "rollback"
    baseline_error_rate: float
    canary_error_rate: float
    tolerance: float

    def __str__(self) -> str:
        return self.decision.upper()


def canary_decision(baseline: float, canary: float, tolerance: float = 0.02) -> CanaryResult:
    """Compare the canary's error rate to the running version's. Nobody has to notice."""
    decision = "promote" if canary <= baseline + tolerance else "rollback"
    return CanaryResult(decision, baseline, canary, tolerance)


SLOS = {
    "triage_latency_p95_ms": 3000,      # ceiling: 95% of triages under 3 seconds
    "escalation_accuracy": 0.95,        # floor: correct escalate/hold decisions
}


def check_slos(observed: dict) -> dict:
    breaches = {}
    if observed.get("triage_latency_p95_ms", 0) > SLOS["triage_latency_p95_ms"]:
        breaches["triage_latency_p95_ms"] = {"observed": observed["triage_latency_p95_ms"],
                                             "ceiling": SLOS["triage_latency_p95_ms"]}
    if observed.get("escalation_accuracy", 1.0) < SLOS["escalation_accuracy"]:
        breaches["escalation_accuracy"] = {"observed": observed["escalation_accuracy"],
                                           "floor": SLOS["escalation_accuracy"]}
    return {"healthy": not breaches, "breaches": breaches, "alert": bool(breaches)}
