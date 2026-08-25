"""
Chapter 4 smoke test: intent, extraction, elicitation, interruption.
Exits non-zero if any expectation fails, so CI can run it.

    python labs/chapter-04-conversational-agents-slot-filling/demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import soc                                                    # noqa: E402
from intake.intent import classify_intent, split_multi_intent, handle_turn  # noqa: E402
from intake.slot_filling import (IntakeState, apply_extraction,            # noqa: E402
                                 extract_slots, to_incident, REQUIRED_SLOTS)


def main() -> int:
    v = classify_intent("I got a phishing email and also my VPN is broken")
    assert v["multi_intent"] and v["all_intents"] == ["report_phishing", "it_helpdesk"], v
    actions = {a["intent"]: a["action"] for a in split_multi_intent(
        "I got a phishing email and also my VPN is broken")}
    assert actions == {"report_phishing": "handle", "it_helpdesk": "hand_off"}, actions
    print("intent      ok  multi-intent detected; helpdesk half handed off")

    found = extract_slots(soc.PHISHING_REPORT)
    assert len(found) == len(REQUIRED_SLOTS), found
    assert found["malicious_url"] == "hxxp://it-support-reset[.]example", found
    assert found["approx_time"] == "8:40am", found
    print(f"extraction  ok  {len(found)}/{len(REQUIRED_SLOTS)} slots, no trailing punctuation")

    complete = apply_extraction(IntakeState(), soc.PHISHING_REPORT)
    assert complete.complete() and to_incident(complete)["category"] == "phishing"
    vague = apply_extraction(IntakeState(), soc.VAGUE_REPORT)
    assert vague.missing() == ["sender", "malicious_url", "clicked", "approx_time"], vague
    print("elicitation ok  complete report costs 0 questions; vague report asks for sender")

    state = apply_extraction(IntakeState(), "I think I got a phishing email")
    pending = state.next_question()
    t1 = handle_turn(state, "wait, am I already compromised?", apply_extraction, lambda q: "no")
    assert t1["kind"] == "interruption" and t1["resumed_question"] == pending, t1
    t2 = handle_turn(t1["state"], "it was from helpdesk@it-support-reset.example",
                     apply_extraction, lambda q: "no")
    assert t2["kind"] == "answer" and t2["state"].slots["sender"].endswith(".example"), t2
    print("interrupt   ok  answered, resumed the same question, then captured the slot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
