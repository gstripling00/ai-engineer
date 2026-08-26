"""
Lab 8C smoke test: Chapter 8's team over the real A2A protocol, in-process.

    python labs/chapter-08c-real-a2a/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a2a_team.orchestrator import run_in_process, soc   # noqa: E402


def main() -> int:
    out = run_in_process(soc.SEED_ALERT, trace_id="inc-8c")
    assert sorted(out["cards"]) == ["investigation", "reporting", "triage"]
    assert all("tool:create_ticket" in s.tags for s in out["cards"]["reporting"].skills)
    print("discovery   ok  three agent cards resolved; reporting advertises create_ticket")

    assert out["hops"] == ["triage -> investigation", "investigation -> reporting", "reporting -> orchestrator"], out["hops"]
    assert all(t["state"] == "TASK_STATE_COMPLETED" and t["context_id"] == "inc-8c" for t in out["tasks"])
    assert len({t["task_id"] for t in out["tasks"]}) == 3
    print("tasks       ok  three tasks, each completed, all sharing context_id inc-8c")

    final = out["final"].payload
    assert final["verdict"] == "confirmed_compromise" and final["ticket"]["id"].startswith("INC-")
    writers = {a for a, t, ok in out["audit"] if t == "create_ticket" and ok}
    assert writers == {"reporting"} and len(soc.TICKETS) == 1
    print("verdict     ok  same verdict and single writer as Chapter 8, over the wire protocol")
    return 0


if __name__ == "__main__":
    sys.exit(main())
