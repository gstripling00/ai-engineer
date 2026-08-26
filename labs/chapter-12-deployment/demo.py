"""
Chapter 12 smoke test. Exits non-zero if any expectation fails, so CI can run it.

    python labs/chapter-12-deployment/demo.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deployment.deploy import eval_gate, canary_decision, check_slos                    # noqa: E402
from deployment.release_policy import (stage_model, stage_cost, incident_cost, STAGE_TOKENS,  # noqa: E402
                                       FAST_MODEL, STRONG_MODEL, retirement_warnings,
                                       PRICES_VERIFIED, cost_gate, release)

T = {"recall": 0.90, "precision": 0.85}


def main() -> int:
    assert eval_gate({"recall": 0.94, "precision": 0.91}, T)["passed"]
    bad = eval_gate({"recall": 0.71, "precision": 0.93}, T)
    assert not bad["passed"] and list(bad["failures"]) == ["recall"]
    print("gate        ok  the higher-precision release is blocked on recall")

    assert [canary_decision(0.02, c).decision for c in (0.025, 0.15, 0.008)] == ["promote", "rollback", "promote"]
    print("canary      ok  promote / rollback / promote")

    assert check_slos({"triage_latency_p95_ms": 2100, "escalation_accuracy": 0.97})["healthy"]
    assert list(check_slos({"triage_latency_p95_ms": 5200, "escalation_accuracy": 0.97})["breaches"]) == ["triage_latency_p95_ms"]
    assert list(check_slos({"triage_latency_p95_ms": 2100, "escalation_accuracy": 0.88})["breaches"]) == ["escalation_accuracy"]
    print("slos        ok  ceiling and floor breach separately")

    assert stage_model("investigation") == STRONG_MODEL and stage_model("triage") == FAST_MODEL
    routed, strong = incident_cost("routed"), incident_cost("all_strong")
    assert 0 < routed < strong and abs(sum(stage_cost(s, stage_model(s)) for s in STAGE_TOKENS) - routed) < 1e-12
    print(f"routing     ok  routed ${routed:.5f} vs all-strong ${strong:.5f} ({100*(strong-routed)/strong:.0f}% saved)")

    w = retirement_warnings(today=date.fromisoformat(PRICES_VERIFIED))
    assert w and w[0]["model"] == STRONG_MODEL and "retires" in w[0]
    assert any("stale" in x["retires"] for x in retirement_warnings(today=date(2030, 1, 1)))
    print("dates       ok  retirement warning present; stale-table warning appears when old")

    base = {"triage": 100, "investigation": 10}
    assert cost_gate(base, {"triage": 120, "investigation": 5})["passed"]
    p = cost_gate(base, {"triage": 100, "investigation": 40})
    assert not p["passed"] and p["reason"] == "cost_regression"
    out = release({"recall": 0.97, "precision": 0.88}, T, {"triage": 100, "investigation": 40}, base,
                  0.022, {"triage_latency_p95_ms": 2100, "escalation_accuracy": 0.97},
                  eval_gate, canary_decision, check_slos)
    assert out["released"] and any(v.startswith("WARN") for _n, v in out["steps"])
    blocked = release({"recall": 0.71, "precision": 0.93}, T, base, base, 0.02,
                      {"triage_latency_p95_ms": 2100, "escalation_accuracy": 0.97},
                      eval_gate, canary_decision, check_slos)
    assert not blocked["released"]
    print("policy      ok  cost regression warns and the recall improvement ships; quality regression blocks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
