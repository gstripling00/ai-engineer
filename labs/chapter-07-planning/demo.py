"""
Chapter 7 smoke test. Exits non-zero if any expectation fails, so CI can run it.

    python labs/chapter-07-planning/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from planning.tools import INCIDENT                                          # noqa: E402
from planning.reasoning import chain_of_thought, select_tool                 # noqa: E402
from planning.planner import make_plan, execute_plan, summarize, reflect     # noqa: E402
from scratch.triage_agent import run as react_run                            # noqa: E402


def main() -> int:
    cot = chain_of_thought(INCIDENT)
    assert len(cot["thought"]) >= 3 and cot["conclusion"]
    print("cot         ok  reasoning is an inspectable list plus a conclusion")

    react = react_run(verbose=False)
    actions = [a for a, _o in react["trajectory"]]
    assert actions == ["ip_reputation", "get_user_context", "final"], actions
    print("react       ok  action/observation trajectory ends in a final answer")

    plan = make_plan(INCIDENT)
    assert [s.name for s in plan][0] == "correlate auth failures" and plan[0].fallback
    healthy = execute_plan(make_plan(INCIDENT))
    assert not healthy.replanned and summarize(healthy)["verdict"] == "confirmed_compromise"
    degraded = execute_plan(make_plan(INCIDENT), unavailable_tools={"auth_fail_1h"})
    assert degraded.replanned and degraded.executed[0][1] == "replanned"
    assert summarize(degraded)["verdict"] == "confirmed_compromise"
    print("plan        ok  healthy run confirmed; degraded run replanned and still reached a verdict")

    picks = {g: select_tool(g) for g in ["check whether this ip address is malicious",
                                         "find the auth failure events in the logs",
                                         "is this account privileged",
                                         "look up the history and reputation of this identity"]}
    assert picks["check whether this ip address is malicious"]["tool"] == "ip_reputation"
    assert picks["find the auth failure events in the logs"]["tool"] == "search_logs"
    assert picks["is this account privileged"]["tool"] == "get_user_context"
    assert not picks["look up the history and reputation of this identity"]["confident"]
    print("select      ok  three clear picks, one refusal on a thin margin")

    hollow = execute_plan(make_plan(INCIDENT))
    hollow.executed = [(n, s, "") for n, s, _ in hollow.executed]
    final = reflect(hollow, {"steps": 3, "replanned": False, "reached_reputation": False,
                             "verdict": "confirmed_compromise"})
    assert final["revised"] and final["verdict"] == "inconclusive", final
    ok = reflect(healthy, summarize(healthy))
    assert not ok["revised"], ok
    print("reflect     ok  unsupported claim downgraded to inconclusive; supported claim untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
