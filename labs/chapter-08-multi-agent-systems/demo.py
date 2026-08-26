"""
Chapter 8 smoke test. Exits non-zero if any expectation fails, so CI can run it.

    python labs/chapter-08-multi-agent-systems/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import soc, workers                                                # noqa: E402
from common.a2a import new_investigation                                       # noqa: E402
from common.model import get_model                                             # noqa: E402
from common.workers import TRIAGE_TOOLS, INVEST_TOOLS, REPORT_TOOLS, authorized_call  # noqa: E402
from common.coordination import Delegation, MAX_HANDOFFS, fan_out              # noqa: E402
from common.graph import run_team_graph, checkpoints                           # noqa: E402


def main() -> int:
    soc.reset_tickets()
    model = get_model()
    m = new_investigation(soc.SEED_ALERT, trace_id="inc-4417")
    for stage in (workers.triage, workers.investigate, workers.report):
        m = stage(m, model)
        assert m.trace_id == "inc-4417"
    assert m.to_agent == "orchestrator" and m.payload["ticket"]["severity"] == "critical", m.payload
    assert len(soc.TICKETS) == 1
    print("pipeline    ok  triage -> investigation -> reporting, one trace, one ticket")

    assert "create_ticket" in REPORT_TOOLS and "create_ticket" not in TRIAGE_TOOLS + INVEST_TOOLS
    denied = authorized_call("triage", "create_ticket", {"title": "x", "severity": "low", "summary": ""})
    assert "denied" in denied and len(soc.TICKETS) == 1
    print("privilege   ok  triage's create_ticket attempt denied at the toolset boundary")

    chain = Delegation(trace_id="inc-4417")
    outcomes = [chain.handoff("triage", "investigation", f"hop {i}") for i in range(7)]
    assert [o["ok"] for o in outcomes] == [True] * MAX_HANDOFFS + [False, False], outcomes
    assert outcomes[MAX_HANDOFFS]["reason"] == "max_handoffs exceeded"
    assert outcomes[1]["cycle_detected"] and not outcomes[0]["cycle_detected"]
    print(f"delegation  ok  refused after {MAX_HANDOFFS} hops; repeated edge flagged as a cycle")

    def inv(signal):
        if "auth" in signal or "privilege" in signal:
            return {"verdict": "confirmed_compromise", "severity": "critical"}
        return {"verdict": "inconclusive", "severity": "low"}
    r = fan_out(["failed auth burst", "unusual source ip", "privilege escalation"], inv, trace_id="inc-4417")
    assert r["single_trace"] and not r["any_branch_wrote"] and len(r["branches"]) == 3
    assert r["merged"]["verdict"] == "confirmed_compromise" and r["merged"]["dissent"]
    print("fan-out     ok  three branches, single trace, no writes, dissent reported")

    soc.reset_tickets(); mark = len(workers.AUDIT)
    final = run_team_graph(new_investigation(soc.SEED_ALERT, trace_id="inc-4417"))
    assert final["payload"]["verdict"] == "confirmed_compromise" and final["trace_id"] == "inc-4417"
    assert final["hops"] == ["triage -> investigation", "investigation -> reporting", "reporting -> orchestrator"]
    assert [(e["role"], e["tool"], e["allowed"]) for e in workers.AUDIT[mark:]][:3] == \
        [("triage", "search_logs", True), ("triage", "get_user_context", True), ("investigation", "ip_reputation", True)]
    assert len(checkpoints(new_investigation(soc.SEED_ALERT, trace_id="inc-4417"))) == 5
    print("graph       ok  StateGraph reproduces the loop's verdict, hops and audit; 5 checkpoints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
