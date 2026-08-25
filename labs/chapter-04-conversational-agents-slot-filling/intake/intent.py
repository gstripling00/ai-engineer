"""
Intent recognition and interruption handling.

The trap in intent recognition is returning ONE label. Real messages carry more
than one intent, and the dropped half is often the urgent half. classify_intent
returns every intent it finds; split_multi_intent says what to do with each.

The trap in interruptions is treating every message as an answer to the last
question. handle_turn detects a mid-interview question, answers it, and resumes
the interview from the same pending question instead of restarting it.
"""
import re

# intent -> (keyword cues, what Aegis does with it)
INTENTS = {
    "report_phishing":    (["phish", "suspicious email", "weird email", "scam", "spoof",
                            "asking me to reset", "suspicious link"], "handle"),
    "account_compromise": (["compromised", "hacked", "someone logged in", "locked out",
                            "password changed"], "handle"),
    "it_helpdesk":        (["vpn", "wifi", "printer", "laptop", "my password reset",
                            "install", "broken", "not working"], "hand_off"),
    "general_question":   (["how do i", "what is", "is it safe", "should i"], "handle"),
}

# Intents Aegis owns. Anything else is somebody else's queue — handed off, not dropped.
IN_SCOPE = {"report_phishing", "account_compromise", "general_question"}


def _cues_in(message: str, cues: list) -> list:
    low = message.lower()
    return [c for c in cues if c in low]


def classify_intent(message: str) -> dict:
    """Return every intent present, not just the first one matched.

    {"primary": str | None, "all_intents": [str, ...], "multi_intent": bool}
    """
    found = []
    for intent, (cues, _action) in INTENTS.items():
        if _cues_in(message, cues):
            found.append(intent)
    return {"primary": found[0] if found else None,
            "all_intents": found,
            "multi_intent": len(found) > 1}


def split_multi_intent(message: str) -> list:
    """One entry per intent, each with the action Aegis takes and the cues that fired."""
    actions = []
    for intent in classify_intent(message)["all_intents"]:
        cues, action = INTENTS[intent]
        actions.append({"intent": intent,
                        "action": action if intent in IN_SCOPE else "hand_off",
                        "cues": _cues_in(message, cues)})
    return actions


# A message that opens with one of these, or ends in a question mark, is the user
# changing the subject rather than answering the pending question.
_INTERRUPTION_OPENERS = ("wait", "hold on", "hang on", "actually", "quick question",
                         "before that", "sorry", "one more thing", "also")


def is_interruption(message: str) -> bool:
    text = message.strip().lower()
    return text.endswith("?") or text.startswith(_INTERRUPTION_OPENERS)


def handle_turn(state, message: str, extractor, answer_fn) -> dict:
    """Process one user message during an interview.

    extractor(state, message) -> state    merges any slots found in the message
    answer_fn(message) -> str             answers an off-topic question

    Returns {"kind": "interruption" | "answer", "state": state, "reply": str,
             "resumed_question": str | None}

    A message is treated as an interruption only if it LOOKS like one AND
    extraction finds nothing new in it. "Wait, it was from bob@evil.example?"
    is an answer that happens to be phrased as a question.
    """
    pending = state.next_question()
    before = dict(state.slots)
    state = extractor(state, message)
    learned = {k: v for k, v in state.slots.items() if k not in before}

    if is_interruption(message) and not learned:
        return {"kind": "interruption",
                "state": state,
                "reply": answer_fn(message),
                "resumed_question": pending}          # same question as before

    nxt = state.next_question()
    return {"kind": "answer",
            "state": state,
            "reply": nxt if nxt else "Thanks - that's everything I need.",
            "resumed_question": None}
