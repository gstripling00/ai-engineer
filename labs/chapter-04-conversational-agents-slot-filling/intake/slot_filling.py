"""
Slot filling: the form, the state machine over it, extraction, and elicitation.

Two jobs, kept separate on purpose:
  * extraction  — parse everything the person already told you (extract_slots)
  * elicitation — ask only for what is still missing (IntakeState.next_question)

Conflate them and you get the bot that asks for information the user just gave it.
Extraction here is deterministic pattern matching, so it can only MISS, never
invent. A model-based extractor gains coverage and gains the ability to
hallucinate — see grounded extraction in the notebook.
"""
import json
import re
from dataclasses import dataclass, field

REQUIRED_SLOTS = ["report_type", "sender", "malicious_url", "clicked", "approx_time"]
OPTIONAL_SLOTS = ["attachment_name"]

SLOT_QUESTIONS = {
    "report_type": "What are you reporting - a suspicious email, a suspicious link, or something else?",
    "sender": "What was the sender's email address?",
    "malicious_url": "What URL were you asked to visit? (paste it defanged if you like)",
    "clicked": "Did you click the link or enter any credentials? (yes/no)",
    "approx_time": "Roughly what time did you receive it?",
}


def clean(value: str) -> str:
    """Strip trailing sentence punctuation from an extracted value.

    A URL captured as 'hxxp://bad[.]example.' will not match a blocklist entry
    for 'hxxp://bad[.]example', and will not cluster with the same indicator in
    Chapter 5. Extraction hygiene is an indicator-quality problem.
    """
    return value.rstrip(".,;:!?").strip()


def extract_slots(text: str) -> dict:
    """Pull every required slot the text supports. Deterministic; can only miss."""
    found = {}
    low = text.lower()

    if "email" in low or "phish" in low or "message" in low:
        found["report_type"] = "suspicious_email"

    sender = re.search(r"[\w.\-]+@[\w.\-]+\.\w+", text)
    if sender:
        found["sender"] = clean(sender.group(0))

    # matches a normal URL and a defanged one (hxxp://, [.])
    url = re.search(r"h[xt]{2}ps?://[\w\.\[\]\-/]+", text, re.I)
    if url:
        found["malicious_url"] = clean(url.group(0))

    if re.search(r"did\s*not\s*click|didn'?t\s*click|not\s*click", low):
        found["clicked"] = "no"
    elif re.search(r"\bi\s*clicked|entered\s*(my\s*)?(password|credentials)", low):
        found["clicked"] = "yes"

    when = re.search(r"\b(?:around\s+)?(\d{1,2}[:.]\d{2}\s*[ap]\.?m\.?|\d{1,2}\s*[ap]\.?m\.?)", low)
    if when:
        found["approx_time"] = clean(when.group(1).strip())

    return found


def extract_optional(text: str) -> dict:
    """Optional slots: captured if offered, never asked for."""
    found = {}
    attachment = re.search(r"[\w\-]+\.(pdf|docx?|xlsx?|zip)", text, re.I)
    if attachment:
        found["attachment_name"] = attachment.group(0)
    return found


@dataclass
class IntakeState:
    """The whole of conversation state: filled slots, and three questions the
    agent can answer about itself — what is missing, am I done, what next."""
    slots: dict = field(default_factory=dict)

    def missing(self) -> list:
        return [s for s in REQUIRED_SLOTS
                if s not in self.slots or self.slots[s] in (None, "")]

    def complete(self) -> bool:
        return not self.missing()

    def next_question(self):
        m = self.missing()
        return SLOT_QUESTIONS[m[0]] if m else None


def apply_extraction(state: IntakeState, text: str) -> IntakeState:
    """Run extraction on a message and merge into state. First answer wins:
    a slot already filled is never overwritten by a later message."""
    for slot, value in extract_slots(text).items():
        state.slots.setdefault(slot, value)
    for slot, value in extract_optional(text).items():
        state.slots.setdefault(slot, value)
    return state


def to_incident(state: IntakeState) -> dict:
    """The point of the conversation: a structured record the rest of Aegis can act on.
    An incomplete state cannot become an incident — the guard is explicit."""
    if not state.complete():
        raise ValueError(f"cannot emit an incomplete incident; missing {state.missing()}")
    fingerprint = abs(hash(json.dumps(state.slots, sort_keys=True))) % 10000
    return {"id": f"INTAKE-{fingerprint}", "category": "phishing", **state.slots}
