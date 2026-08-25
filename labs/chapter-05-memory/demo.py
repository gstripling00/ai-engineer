"""
Chapter 5 smoke test. Exits non-zero if any expectation fails, so CI can run it.

    python labs/chapter-05-memory/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memory.context_budget import count_tokens, truncate, sliding_window, summarize_middle  # noqa: E402
from memory.memory_store import (EpisodicMemory, ProceduralMemory,             # noqa: E402
                                 assess_with_memory, is_known_bad_sender)

BAD = "helpdesk@it-support-reset.example"
PLAYBOOK = ["quarantine message", "reset credentials", "notify user"]


def main() -> int:
    msgs = [{"role": "system", "content": "You are Aegis. You may NOT take remediation actions yourself."}]
    for i in range(6):
        msgs.append({"role": "assistant", "content": f"[call] search_logs(query=auth_fail_{i})"})
        msgs.append({"role": "tool", "content": '{"count": 4, "results": [...]}' * 3})
    keeps = {name: any(m["role"] == "system" and "may NOT" in m["content"] for m in fn(msgs, 60))
             for name, fn in (("truncate", truncate), ("sliding_window", sliding_window),
                              ("summarize_middle", summarize_middle))}
    assert keeps == {"truncate": False, "sliding_window": True, "summarize_middle": True}, keeps
    assert all(count_tokens(fn(msgs, 60)) <= 60 for fn in (truncate, sliding_window, summarize_middle))
    print("working     ok  truncate drops the guardrail; window and summary keep it, all within budget")

    ep, pr = EpisodicMemory(), ProceduralMemory()
    labels = []
    for i, user in enumerate(["j.okafor", "m.chen", "a.singh"]):
        rep = {"id": f"INC-{i}", "category": "phishing", "sender": BAD, "user": user}
        a = assess_with_memory(rep, ep, pr)
        ep.record(rep); pr.learn("phishing", PLAYBOOK, succeeded=True)
        labels.append((a["is_campaign"], len(a["related_prior"]), a["recommended_severity"]))
    assert labels == [(False, 0, "medium"), (False, 1, "medium"), (True, 2, "high")], labels
    print("episodic    ok  third report from the same sender is a CAMPAIGN")

    assert is_known_bad_sender(BAD) and not is_known_bad_sender("newsletter@marketing.example")
    print("semantic    ok  known-bad sender lookup")

    p = ProceduralMemory()
    p.learn("phishing", PLAYBOOK, succeeded=False); assert p.recall("phishing") is None
    p.learn("phishing", PLAYBOOK, succeeded=True); p.learn("phishing", PLAYBOOK, succeeded=True)
    p.learn("phishing", ["do nothing"], succeeded=True)
    assert p.recall("phishing") == {"steps": PLAYBOOK, "successes": 2}, p.recall("phishing")
    print("procedural  ok  failures teach nothing; a weak rival never displaces a proven playbook")

    mem = EpisodicMemory()
    for i in range(3):
        mem.record({"id": f"P{i}", "category": "phishing", "sender": BAD})
    mem.record({"id": "N1", "category": "newsletter", "sender": "newsletter@marketing.example"})
    q = f"phishing {BAD}"
    low = [h["id"] for h in mem.recall(q, k=10, threshold=0.05)]
    mid = [h["id"] for h in mem.recall(q, k=10, threshold=0.40)]
    high = [h["id"] for h in mem.recall(q, k=10, threshold=0.80)]
    assert "N1" in low and mid == ["P0", "P1", "P2"] and high == [], (low, mid, high)
    print("threshold   ok  too low admits the newsletter; too high loses the campaign")
    return 0


if __name__ == "__main__":
    sys.exit(main())
