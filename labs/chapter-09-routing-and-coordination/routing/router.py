"""
The routing front door.

Two stages, and confusing them is a security bug:
  semantic  what KIND of alert is this?   a model may guess
  severity  how BAD is it?                policy - never a model

semantic_route() scores an alert against each handler's description. route_scores()
exposes the numbers behind that decision; route_with_confidence() gives the router
permission to refuse when the score is low or the margin over the runner-up is thin.
severity_route() is a lookup table with no model in the path. route_with_fallback()
degrades to a generalist and SAYS SO. build_escalation() hands a human the work
already done, including what the agent could not determine.
"""
import math
import re
from collections import Counter

ROUTE_DESCRIPTIONS = {
    "phishing_handler": "phishing suspicious email malicious url link sender credential harvest",
    "auth_handler":     "authentication failed login brute force account takeover session password",
    "egress_handler":   "data exfiltration egress transfer bytes destination outbound unusual",
}


def vec(text: str) -> Counter:
    return Counter(t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2)


def cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def alert_text(alert: dict) -> str:
    return f'{alert.get("rule", "")} {" ".join(alert.get("signals", []))}'


def _scored(alert: dict, routes: dict | None = None) -> list:
    query = vec(alert_text(alert))
    scored = [(cosine(query, vec(desc)), name) for name, desc in (routes or ROUTE_DESCRIPTIONS).items()]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored


def semantic_route(alert: dict, routes: dict | None = None) -> str:
    """Best-scoring handler. Always answers - even on a score of zero. That is
    what a scoring function does, and it is the problem route_scores() exposes."""
    scored = _scored(alert, routes)
    return scored[0][1] if scored else "auth_handler"


def route_scores(alert: dict, routes: dict | None = None) -> dict:
    scored = _scored(alert, routes)
    top_score, top_route = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    return {"route": top_route, "score": round(top_score, 3), "margin": round(top_score - runner_up, 3)}


def route_with_confidence(alert: dict, min_score: float = 0.15, min_margin: float = 0.05,
                          routes: dict | None = None) -> dict:
    """Route only when the score clears min_score AND the margin clears min_margin.
    Otherwise escalate to a human, and record what the guess would have been."""
    r = route_scores(alert, routes)
    if r["score"] < min_score:
        return {**r, "route": "human_analyst", "confident": False,
                "reason": "below_score_threshold", "would_have_routed_to": r["route"]}
    if r["margin"] < min_margin:
        return {**r, "route": "human_analyst", "confident": False,
                "reason": "ambiguous_margin", "would_have_routed_to": r["route"]}
    return {**r, "confident": True}


def severity_route(severity: str) -> str:
    """Policy. A lookup table, in code, with no model in the path."""
    return "human_analyst" if severity in ("critical", "high") else "auto_handler"


def route_with_fallback(alert: dict, failed_routes: set | None = None) -> dict:
    """If the specialist is down, degrade to a generalist - and say so."""
    failed = failed_routes or set()
    primary = semantic_route(alert)
    if primary not in failed:
        return {"route": primary, "degraded": False}
    return {"route": "generalist_handler", "degraded": True, "reason": f"{primary} unavailable"}


def build_escalation(alert: dict, findings: dict) -> dict:
    """Hand a human the work, not just the alarm."""
    return {
        "action": "human_handoff",
        "alert_id": alert["id"],
        "severity": findings.get("severity", "unknown"),
        "state": {
            "verdict": findings.get("verdict"),
            "evidence": findings.get("evidence", {}),
            "steps_taken": findings.get("steps_taken", []),
            "open_questions": findings.get("open_questions", []),
        },
        "why_escalated": findings.get("why_escalated", "severity policy"),
    }
