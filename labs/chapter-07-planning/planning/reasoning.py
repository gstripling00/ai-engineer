"""
§7.2 chain-of-thought and §7.5 tool selection under ambiguity.

chain_of_thought() produces reasoning as an ARTIFACT - a list of thoughts and a
conclusion you can read and disagree with. Note what it cannot do: it reasons
about what the model already believes; nothing here touches a tool, so it cannot
discover that a log source is down. That is the gap the ReAct loop closes.

select_tool() scores a goal against every tool's description and refuses when the
top two are too close to call. The margin between best and second-best is the
signal: a confident pick at a 0.01 margin is a coin flip that will look like a
judgment in the trace.
"""
import re

from .tools import TOOL_DESCRIPTIONS


def chain_of_thought(incident: dict) -> dict:
    """Deterministic stand-in for a model reasoning step by step. Real models are
    prompted for this; the point is the SHAPE of the output, not its source."""
    thought = [
        f"The alert is categorised {incident['category']} for user {incident['user']} "
        f"from {incident['src_ip']}.",
        "Brute force means repeated failed logins; if a success follows, the account may be taken over.",
        f"I do not yet know whether {incident['src_ip']} is a known-bad address, or whether "
        f"{incident['user']} is privileged.",
        "The verdict depends on evidence I have not gathered: reputation, log history, and privilege.",
    ]
    return {"thought": thought,
            "conclusion": "Likely credential attack; confidence is low until reputation and "
                          "log evidence are retrieved."}


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2}


def select_tool(goal: str, min_margin: float = 0.15) -> dict:
    """Score each tool's description against the goal (word overlap); pick the best
    only if it beats the runner-up by min_margin. Otherwise refuse and say why."""
    g = _words(goal)
    scores = {}
    for tool, desc in TOOL_DESCRIPTIONS.items():
        d = _words(desc)
        scores[tool] = round(len(g & d) / len(g), 3) if g else 0.0
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    (best, s1), (second, s2) = ranked[0], ranked[1]
    margin = round(s1 - s2, 3)
    if s1 == 0:
        return {"confident": False, "tool": None, "margin": 0.0,
                "reason": "no tool matches this goal", "candidates": []}
    if margin < min_margin:
        return {"confident": False, "tool": None, "margin": margin,
                "reason": f"margin {margin} below {min_margin}: {best} vs {second} fit almost equally",
                "candidates": [best, second]}
    return {"confident": True, "tool": best, "margin": margin, "reason": "clear winner",
            "candidates": [best, second]}
