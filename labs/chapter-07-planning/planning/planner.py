"""
§7.4 plan-and-solve with dynamic replanning, and §7.6 reflection.

A plan is a list of Steps decided BEFORE anything runs. A printed plan can be
reviewed and stopped. Each step may carry a fallback; if the primary source is
unavailable the executor uses it and RECORDS that it did - a silent substitution
that reports the same confidence is a lie by omission.

reflect() is not a retry. It is a reviewer: it reads the evidence, compares it to
the draft verdict, and has the authority to overrule the draft and the obligation
to say why. Replanning catches broken plumbing; reflection catches confident nonsense.
"""
import json
from dataclasses import dataclass, field

from .tools import call_tool


@dataclass
class Step:
    name: str
    tool: str
    args: dict
    fallback: dict | None = None      # {"tool": ..., "args": ...} if the primary fails


@dataclass
class PlanResult:
    executed: list = field(default_factory=list)   # (name, status, observation)
    replanned: bool = False


def make_plan(incident: dict) -> list:
    ip, user = incident["src_ip"], incident["user"]
    return [
        Step("correlate auth failures", "search_logs", {"query": "auth_fail", "window": "1h"},
             fallback={"tool": "search_logs", "args": {"query": user, "window": "24h"}}),
        Step("check source IP reputation", "ip_reputation", {"ip": ip}),
        Step("assess user privilege", "get_user_context", {"user": user}),
    ]


def execute_plan(plan: list, unavailable_tools: set | None = None) -> PlanResult:
    """Run each step. If its primary source is unavailable, use the fallback and
    record the repair. `unavailable_tools` names sources by '<query>_<window>'."""
    unavailable = unavailable_tools or set()
    result = PlanResult()
    for step in plan:
        source = f"{step.args.get('query', step.tool)}_{step.args.get('window', '')}".rstrip("_")
        if source not in unavailable and step.tool not in unavailable:
            result.executed.append((step.name, "ok", call_tool(step.tool, step.args)))
            continue
        if step.fallback:                                   # REPLAN, and say so
            result.replanned = True
            fb = step.fallback
            result.executed.append((step.name, "replanned", call_tool(fb["tool"], fb["args"])))
        else:
            result.executed.append((step.name, "failed", json.dumps({"error": "no fallback"})))
    return result


def _observations(result: PlanResult) -> list:
    out = []
    for _name, _status, obs in result.executed:
        try:
            out.append(json.loads(obs))
        except (ValueError, TypeError):
            out.append(None)
    return out


def summarize(result: PlanResult) -> dict:
    """Mechanical summary of a run. It reports what happened; it cannot tell you
    whether the conclusion is justified - that is reflect()'s job."""
    parsed = [o for o in _observations(result) if isinstance(o, dict)]
    reached_reputation = any("verdict" in o for o in parsed)
    malicious = any(o.get("verdict") == "malicious" for o in parsed)
    return {
        "steps": len(result.executed),
        "replanned": result.replanned,
        "reached_reputation": reached_reputation,
        "verdict": "confirmed_compromise" if (reached_reputation and malicious) else "inconclusive",
    }


def reflect(result: PlanResult, draft: dict) -> dict:
    """Review the draft against the evidence. Downgrades an unsupported verdict and
    records every reason."""
    parsed = [o for o in _observations(result) if isinstance(o, dict)]
    evidence = {
        "malicious_reputation": any(o.get("verdict") == "malicious" for o in parsed),
        "observations": sum(1 for _n, _s, o in result.executed if o),
    }
    verdict, critique = draft["verdict"], []

    if verdict == "confirmed_compromise" and not evidence["malicious_reputation"]:
        critique.append("draft claims compromise but no reputation source returned "
                        "'malicious' - downgrading to 'suspected'")
        verdict = "suspected_compromise"

    if evidence["observations"] < 2 and verdict != "inconclusive":
        critique.append("fewer than two evidence-bearing observations - a verdict "
                        "cannot rest on a single source; downgrading to 'inconclusive'")
        verdict = "inconclusive"

    if result.replanned and verdict == "confirmed_compromise":
        critique.append("a primary source was substituted during this run; confidence "
                        "should be stated with that caveat")

    if not critique:
        critique.append("evidence supports the draft verdict; no revision needed")

    return {**draft, "verdict": verdict, "reflection": critique,
            "revised": verdict != draft["verdict"]}
