"""
Chapter 9 smoke test. Exits non-zero if any expectation fails, so CI can run it.

    python labs/chapter-09-routing-and-coordination/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from routing.router import (semantic_route, route_scores, route_with_confidence,   # noqa: E402
                            severity_route, route_with_fallback, build_escalation)
from routing.mcp_discovery import build_capability_server, discover_routes, route_via_discovery  # noqa: E402

ALERTS = [
    {"id": "A-1", "rule": "Possible phishing email", "signals": ["suspicious link", "credential harvest"], "severity": "medium"},
    {"id": "A-2", "rule": "Brute force detected", "signals": ["repeated failed login", "account takeover"], "severity": "critical"},
    {"id": "A-3", "rule": "Large outbound transfer", "signals": ["data egress", "unusual destination"], "severity": "high"},
    {"id": "A-4", "rule": "Anomalous printer firmware update", "signals": ["unknown protocol", "no signature"], "severity": "low"},
]


def main() -> int:
    routes = [semantic_route(a) for a in ALERTS]
    assert routes[:3] == ["phishing_handler", "auth_handler", "egress_handler"], routes
    print("semantic    ok  three alerts routed to the right handler")

    conf = [route_with_confidence(a) for a in ALERTS]
    assert all(c["confident"] for c in conf[:3]) and not conf[3]["confident"], conf
    assert conf[3]["route"] == "human_analyst" and conf[3]["reason"] == "below_score_threshold"
    assert route_scores(ALERTS[3])["score"] == 0.0
    print("confidence  ok  A-4 escalated on a zero score instead of a confident guess")

    assert [severity_route(s) for s in ("low", "medium", "high", "critical")] == \
        ["auto_handler", "auto_handler", "human_analyst", "human_analyst"]
    assert len({severity_route("critical") for _ in range(50)}) == 1
    print("severity    ok  policy lookup, deterministic")

    fb = route_with_fallback(ALERTS[0], failed_routes={"phishing_handler"})
    assert fb["degraded"] and fb["route"] == "generalist_handler"
    print("fallback    ok  degraded to a generalist and flagged it")

    esc = build_escalation(ALERTS[1], {"severity": "critical", "verdict": "confirmed_compromise",
                                       "open_questions": ["other accounts?"]})
    assert esc["state"]["open_questions"] and esc["action"] == "human_handoff"
    print("escalation  ok  hands over verdict, evidence, steps, open questions")

    fw = {"id": "A-9", "rule": "Anomalous printer firmware update",
          "signals": ["unsigned firmware", "unknown protocol", "device management"]}
    before = discover_routes(build_capability_server())
    assert sorted(before) == ["auth_handler", "egress_handler", "phishing_handler"]
    assert not route_via_discovery(fw, before)["confident"]
    new = {"name": "device_handler", "description": "Handles device and firmware security: unsigned firmware, printer, IoT, device management, unknown protocol."}
    after = discover_routes(build_capability_server(extra_tools=[new]))
    d = route_via_discovery(fw, after)
    assert "device_handler" in after and d["confident"] and d["route"] == "device_handler", d
    print("discovery   ok  handler published server-side became routable with no client change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
