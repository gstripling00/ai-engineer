"""
Lab 8B smoke test: the same team, three orchestrators, one verdict.

    python labs/chapter-08b-the-same-team-three-ways/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frameworks.team import soc                                     # noqa: E402
from frameworks.scratch_team import run_scratch                     # noqa: E402
from frameworks.langgraph_team import run_langgraph, checkpoint_history  # noqa: E402
from frameworks.adk_team import run_adk, fan_out_workflow           # noqa: E402


def main() -> int:
    runs = [run_scratch(soc.SEED_ALERT, "inc-8b"), run_langgraph(soc.SEED_ALERT, "inc-8b"), run_adk(soc.SEED_ALERT, "inc-8b")]
    verdicts = {r.verdict for r in runs}; audits = {tuple(r.audit) for r in runs}; hops = {tuple(r.hops) for r in runs}
    assert verdicts == {"confirmed_compromise"} and len(audits) == 1 and len(hops) == 1, (verdicts, audits, hops)
    assert all(r.trace_id == "inc-8b" for r in runs)
    writers = {a for a, t, ok in runs[0].audit if t == "create_ticket" and ok}
    assert writers == {"reporting"}
    print("three ways  ok  same verdict, same handoffs, same audit, one trace, one writer")

    hist = checkpoint_history(soc.SEED_ALERT, "inc-8b")
    assert len(hist) >= 4 and hist[-1]["next"] == ()
    print(f"langgraph   ok  {len(hist)} checkpoints; resumable from any node")

    def inv(signal):
        return {"verdict": "confirmed_compromise" if "auth" in signal else "inconclusive"}
    merged = fan_out_workflow(["failed auth burst", "unusual source ip"], inv)
    assert merged["branches"] == 2 and merged["dissent"]
    print("adk         ok  fan-out through a JoinNode; dissent reported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
