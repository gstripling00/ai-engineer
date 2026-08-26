"""
§8.3.3 bounded delegation and §8.4 parallel execution.

Delegation counts handoffs on ONE envelope's trace and refuses past MAX_HANDOFFS.
The bound lives in the envelope, not in any agent's memory - the multi-agent
equivalent of Chapter 1's max_steps. A cycle (A -> B -> A) is detected and
reported; it is not automatically wrong, but an unbounded one is.

fan_out() runs one investigator per signal concurrently, keeps the trace single,
checks that no branch wrote to the world, and merges by taking the most severe
verdict while REPORTING dissent rather than averaging it away.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import soc

MAX_HANDOFFS = 5

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
VERDICT_RANK = {"inconclusive": 0, "suspected_compromise": 1, "confirmed_compromise": 2}


@dataclass
class Delegation:
    trace_id: str
    max_handoffs: int = MAX_HANDOFFS
    history: list = field(default_factory=list)      # (from_agent, to_agent, reason)

    def handoff(self, from_agent: str, to_agent: str, reason: str) -> dict:
        if len(self.history) >= self.max_handoffs:
            return {"ok": False, "reason": "max_handoffs exceeded", "hops": len(self.history),
                    "cycle_detected": self._cycle(from_agent, to_agent)}
        cycle = self._cycle(from_agent, to_agent)
        self.history.append((from_agent, to_agent, reason))
        return {"ok": True, "reason": reason, "hops": len(self.history), "cycle_detected": cycle}

    def _cycle(self, from_agent: str, to_agent: str) -> bool:
        """True if this handoff sends work back along an edge already used."""
        return any(f == from_agent and t == to_agent for f, t, _ in self.history)


def merge(branches: list) -> dict:
    """Most severe verdict wins - safe and expensive. Disagreement is reported."""
    verdicts = sorted({b["verdict"] for b in branches}, key=lambda v: -VERDICT_RANK.get(v, 0))
    severity = max((b["severity"] for b in branches), key=lambda s: SEVERITY_RANK.get(s, 0))
    return {"verdict": verdicts[0], "severity": severity,
            "dissent": len(verdicts) > 1, "distinct_verdicts": verdicts}


def fan_out(signals: list, investigator, trace_id: str, max_workers: int | None = None) -> dict:
    tickets_before = len(soc.TICKETS)

    def branch(signal: str) -> dict:
        out = investigator(signal)
        return {"signal": signal, "trace_id": trace_id, **out}

    with ThreadPoolExecutor(max_workers=max_workers or len(signals)) as pool:
        branches = list(pool.map(branch, signals))

    return {"trace_id": trace_id,
            "branches": branches,
            "single_trace": all(b["trace_id"] == trace_id for b in branches),
            "any_branch_wrote": len(soc.TICKETS) != tickets_before,
            "merged": merge(branches)}
