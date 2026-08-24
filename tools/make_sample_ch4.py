#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 4 sample notebook.

Same contract as the Chapter 1-3 samples: no repo clone, no pip install, no API
key. Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 4's claim: a conversational agent is a state machine over a form.
Extraction (parse what is present) and elicitation (ask only for what is missing)
are different jobs, and conflating them produces the re-interviewing bot everyone
hates.

    python tools/make_sample_ch4.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch04", "Aegis_Chapter4_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 4 — Conversational Agents",
       "",
       "So far Aegis has been handed clean, structured alerts. Real security work does not",
       "start that way. It starts with a human typing something like:",
       "",
       "> *\"Hi security team, I got a weird email this morning claiming to be from IT...\"*",
       "",
       "Someone has to turn that into a structured incident record. Traditionally that is a",
       "form, and people fill forms badly. An agent can do better — but only if it is built",
       "as a state machine over that form, not as a chatbot with good manners.",
       "",
       "Two jobs, and they are different:",
       "",
       "1. **Extraction** — parse everything the person already told you.",
       "2. **Elicitation** — ask only for what is still missing.",
       "",
       "Conflate them and you build the bot that asks for information the user just gave it.",
       "Everyone has met that bot. This notebook builds the one that does not.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## The form",
       "",
       "Before anything conversational, decide what \"done\" means. Five slots must be filled",
       "before triage can act on a phishing report.",
       "",
       "This list is the agent's definition of complete. It is also, quietly, a product",
       "decision: every slot you mark required is a question someone must answer."),
    code('''import json
import re
from dataclasses import dataclass, field

REQUIRED_SLOTS = ["report_type", "sender", "malicious_url", "clicked", "approx_time"]

SLOT_QUESTIONS = {
    "report_type": "What are you reporting - a suspicious email, a suspicious link, or something else?",
    "sender": "What was the sender's email address?",
    "malicious_url": "What URL were you asked to visit? (paste it defanged if you like)",
    "clicked": "Did you click the link or enter any credentials? (yes/no)",
    "approx_time": "Roughly what time did you receive it?",
}

for slot in REQUIRED_SLOTS:
    print(f'{slot:15} {SLOT_QUESTIONS[slot]}')'''),

    md("## The state",
       "",
       "The agent's entire conversational state is a dictionary of filled slots, plus three",
       "questions it can answer about itself: what is missing, am I done, and what should I",
       "ask next.",
       "",
       "That is the whole of \"conversation management\" at this level. There is no magic in",
       "it, and that is worth knowing — a great deal of chatbot complexity is people",
       "reinventing this badly."),
    code('''@dataclass
class IntakeState:
    slots: dict = field(default_factory=dict)

    def missing(self) -> list:
        return [s for s in REQUIRED_SLOTS
                if s not in self.slots or self.slots[s] in (None, "")]

    def complete(self) -> bool:
        return not self.missing()

    def next_question(self):
        m = self.missing()
        return SLOT_QUESTIONS[m[0]] if m else None


state = IntakeState()
print("missing at the start:", state.missing())
print("complete?           ", state.complete())
print("first question:     ", state.next_question())'''),

    md("## Extraction",
       "",
       "The employee's first message usually contains most of the form already. Extraction",
       "pulls out whatever is there.",
       "",
       "The rules below are deterministic pattern matching. A real system prompts a model to",
       "return JSON — which handles phrasing you did not anticipate, and can also invent a",
       "sender address that was never in the text. That tradeoff gets its own section at the",
       "end of this notebook, because it matters more than it looks.",
       "",
       "Note the defanged-URL pattern (`hxxp://`). Security people write links that way on",
       "purpose so nobody clicks them. An extractor that does not know that will miss the",
       "single most important field in the report."),
    code('''def clean(value: str) -> str:
    """Strip trailing sentence punctuation from an extracted value.

    This matters more than it looks. A URL captured as
    'hxxp://bad[.]example.' will not match a blocklist entry for
    'hxxp://bad[.]example'. Extraction hygiene is an indicator-quality problem.
    """
    return value.rstrip(".,;:!?").strip()


def extract_slots(text: str) -> dict:
    found = {}
    low = text.lower()

    if "email" in low or "phish" in low or "message" in low:
        found["report_type"] = "suspicious_email"

    sender = re.search(r"[\\w.\\-]+@[\\w.\\-]+\\.\\w+", text)
    if sender:
        found["sender"] = clean(sender.group(0))

    # matches both a normal URL and a defanged one (hxxp://, [.] )
    url = re.search(r"h[xt]{2}ps?://[\\w\\.\\[\\]\\-/]+", text, re.I)
    if url:
        found["malicious_url"] = clean(url.group(0))

    if re.search(r"did\\s*not\\s*click|didn'?t\\s*click|not\\s*click", low):
        found["clicked"] = "no"
    elif re.search(r"\\bi\\s*clicked|entered\\s*(my\\s*)?(password|credentials)", low):
        found["clicked"] = "yes"

    when = re.search(r"\\b(?:around\\s+)?(\\d{1,2}[:.]\\d{2}\\s*[ap]\\.?m\\.?|\\d{1,2}\\s*[ap]\\.?m\\.?)", low)
    if when:
        found["approx_time"] = clean(when.group(1).strip())

    return found


REPORT = (
    "Hi security team, I got a weird email this morning claiming to be from IT "
    "asking me to reset my password at hxxp://it-support-reset[.]example. I did "
    "NOT click it. Sender was helpdesk@it-support-reset.example. Around 8:40am."
)

extracted = extract_slots(REPORT)
for slot, value in extracted.items():
    print(f'{slot:15} {value}')

print()
print(f"{len(extracted)} of {len(REQUIRED_SLOTS)} slots filled from the first message alone")'''),

    md("### Why `clean()` is there",
       "",
       "The URL regex happily swallows the sentence's full stop, so a naive extractor",
       "returns `hxxp://it-support-reset[.]example.` — with a trailing period. It looks",
       "harmless. It is not: that string will not match a blocklist entry, will not join a",
       "campaign cluster in Chapter 5, and will not correlate with the same indicator seen",
       "elsewhere. A one-character difference silently breaks every downstream comparison.",
       "",
       "Extraction hygiene is an indicator-quality problem, and it is the kind of bug that",
       "passes every test that only checks whether a field is *present*."),

    md("Five of five. This particular employee wrote an unusually complete report — which is",
       "exactly the case where a naive bot embarrasses itself by asking all five questions",
       "anyway.",
       "",
       "The fix is one line, and it is the heart of the chapter: **extract before you ask.**"),

    md("## Elicitation",
       "",
       "Now the loop. Apply extraction to every message, then ask for the first thing still",
       "missing. Repeat until the form is complete.",
       "",
       "Note `setdefault`: a slot already filled is never overwritten by a later message.",
       "That is a deliberate policy — first answer wins — and you should decide it",
       "consciously rather than inherit it from whichever line of code ran last."),
    code('''def apply_extraction(state: IntakeState, text: str) -> IntakeState:
    for slot, value in extract_slots(text).items():
        state.slots.setdefault(slot, value)     # first answer wins
    return state


def intake(messages: list, verbose: bool = True) -> IntakeState:
    """messages: what the employee says, in order. A real UI would await them."""
    state = IntakeState()
    reply_index = 0

    # The opening report, before any question is asked.
    state = apply_extraction(state, messages[reply_index])
    reply_index += 1
    if verbose:
        print(f"  employee : {messages[0][:66]}...")

    for _ in range(6):
        if state.complete():
            break

        question = state.next_question()
        if verbose:
            print(f"  aegis    : {question}")

        if reply_index < len(messages):
            answer = messages[reply_index]
            reply_index += 1
        else:
            answer = "n/a"

        if verbose:
            print(f"  employee : {answer}")
        state = apply_extraction(state, answer)

    return state


print("intake loop defined")'''),

    md("## The complete report",
       "",
       "The employee told us everything up front. Watch how many questions the agent asks."),
    code('''state = intake([REPORT])

print()
print("questions asked:", 0 if state.complete() else len(state.missing()))
print("complete:", state.complete())
print()
print(json.dumps(state.slots, indent=2))'''),

    md("Expected output:",
       "",
       "```",
       "  employee : Hi security team, I got a weird email this morning claiming to be ...",
       "",
       "questions asked: 0",
       "complete: True",
       "",
       "{",
       '  "report_type": "suspicious_email",',
       '  "sender": "helpdesk@it-support-reset.example",',
       '  "malicious_url": "hxxp://it-support-reset[.]example",',
       '  "clicked": "no",',
       '  "approx_time": "8:40am"',
       "}",
       "```",
       "",
       "Zero questions. The employee wrote one paragraph and the agent produced a complete",
       "structured incident. That is the best possible conversational experience: no",
       "conversation at all."),

    md("## The incomplete report",
       "",
       "Now the realistic case. Someone types a sentence and hits send.",
       "",
       "This is where elicitation earns its keep — and where you can see it asking for",
       "exactly what it lacks, in order, without re-asking anything."),
    code('''VAGUE = "I think I got a phishing email this morning"

state = intake([
    VAGUE,
    "it was from helpdesk@it-support-reset.example",
    "the link was hxxp://it-support-reset[.]example",
    "no I did not click it",
    "around 8:40am",
])

print()
print("complete:", state.complete())
print(json.dumps(state.slots, indent=2))'''),

    md("Four questions, four answers, one complete record. Each question targeted exactly",
       "the gap: it never re-asked the sender once the sender was known.",
       "",
       "That is the difference between a state machine over a form and a chatbot that starts",
       "the interview over every time you say something."),

    md("## Out-of-order answers",
       "",
       "Humans do not answer the question you asked. They answer the question you asked",
       "three questions ago, and volunteer two things you were about to ask.",
       "",
       "Because extraction runs on *every* message, the agent absorbs whatever arrives",
       "whenever it arrives. Watch: the employee answers a question about the link by also",
       "supplying the time."),
    code('''state = intake([
    "someone sent me a dodgy message",
    "the sender was helpdesk@it-support-reset.example and it came in around 8:40am",
    "the link was hxxp://it-support-reset[.]example, and no, I didn't click it",
])

print()
print("complete:", state.complete())
print("slots:", list(state.slots))'''),

    md("Two employee messages after the opener, and the form is full — because one of them",
       "answered three slots at once and the agent noticed.",
       "",
       "A bot that only listened for the answer to *its* question would have needed five",
       "turns and annoyed a person who had already told it everything."),

    md("## Emitting the incident",
       "",
       "The point of the conversation is not the conversation. It is this: a structured",
       "record that the rest of the system can act on.",
       "",
       "Everything from Chapter 5 onward consumes objects that look like this."),
    code('''def to_incident(state: IntakeState) -> dict:
    if not state.complete():
        raise ValueError(f"cannot emit an incomplete incident; missing {state.missing()}")
    fingerprint = abs(hash(json.dumps(state.slots, sort_keys=True))) % 10000
    return {"id": f"INTAKE-{fingerprint}", "category": "phishing", **state.slots}


incident = to_incident(state)
print(json.dumps(incident, indent=2))'''),

    md("Note the guard: an incomplete state cannot become an incident. The type system will",
       "not save you here, so the check is explicit. A half-filled incident record flowing",
       "into triage is a bug that surfaces three chapters later, wearing a disguise."),

    md("## Required versus optional",
       "",
       "One more design decision worth making on purpose. Not every field should block",
       "completion.",
       "",
       "An attachment name is useful when it exists and absurd as a blocking question when",
       "it does not. Optional slots get captured if offered and never asked for."),
    code('''OPTIONAL_SLOTS = ["attachment_name"]


def extract_optional(text: str) -> dict:
    found = {}
    attachment = re.search(r"[\\w\\-]+\\.(pdf|docx?|xlsx?|zip)", text, re.I)
    if attachment:
        found["attachment_name"] = attachment.group(0)
    return found


with_attachment = extract_optional("it had a file called invoice_march.pdf attached")
without = extract_optional("just a link, no attachment")

print("captured when offered:", with_attachment)
print("absent when not:      ", without)
print()
print("blocks completion?", "attachment_name" in REQUIRED_SLOTS)'''),

    md("## The honest limit of this extractor",
       "",
       "The rules above are deterministic, which means they can only *miss*. They cannot",
       "invent.",
       "",
       "Swap in a model and you gain coverage — it will handle phrasings you never",
       "anticipated. You also gain the ability to hallucinate a sender address into a",
       "security incident record. Watch what that looks like."),
    code('''# A model, asked to extract from a vague report, "helpfully" guesses.
model_proposed = {
    "report_type": "suspicious_email",
    "sender": "ceo@yourcompany.example",       # never appeared in the text
    "clicked": "no",
}

VAGUE_REPORT = "I got a suspicious email this morning"


def grounded_extract(text: str, proposed: dict) -> dict:
    """Accept a proposed slot value only if the text actually supports it."""
    low = text.lower()
    accepted, rejected = {}, {}
    for slot, value in proposed.items():
        if isinstance(value, str) and "@" in value and value.lower() not in low:
            rejected[slot] = value          # an address that isn't in the text
        else:
            accepted[slot] = value
    return {"accepted": accepted, "rejected": rejected}


result = grounded_extract(VAGUE_REPORT, model_proposed)
print("accepted:", result["accepted"])
print("rejected:", result["rejected"])'''),

    md("That rejected address is not a hypothetical. Without grounding, it enters an incident",
       "record, and somebody's CEO becomes the subject of a phishing investigation that never",
       "happened.",
       "",
       "The rule to carry forward: **a model may propose; only the text may confirm.** Chapter",
       "10 gives you the tools to measure how often the model proposes things the text does",
       "not support."),

    md("---",
       "",
       "## What you built",
       "",
       "A stateful intake agent: a form, a state machine over it, extraction on every turn,",
       "and elicitation targeted at the gap — emitting a structured incident that the rest of",
       "Aegis can consume.",
       "",
       "Four things to take away:",
       "",
       "- **Extract before you ask.** The user usually told you already.",
       "- **Elicit the gap, not the form.** One question, not a re-interview.",
       "- **Decide required versus optional deliberately.** Every required slot is a question",
       "  someone must answer.",
       "- **A model may propose; only the text may confirm.** Grounding is not a nicety when",
       "  the output is an accusation.",
       "",
       "Chapter 5 gives Aegis memory, and the third phishing report from this same sender",
       "this week stops looking like an isolated incident and starts looking like a campaign.",
       "",
       "### Moving to the companion repository",
       "",
       "```python",
       "REPO_URL = \"https://github.com/<your-org>/<your-repo>.git\"",
       "",
       "import os, sys, subprocess",
       "",
       "if not os.path.isdir(\"aegis\"):",
       "    subprocess.run([\"git\", \"clone\", REPO_URL, \"aegis\"], check=True)   # fails loudly",
       "os.chdir(\"aegis\")",
       "sys.path.insert(0, os.path.abspath(\".\"))",
       "```")
]


def main():
    nb = {"cells": CELLS,
          "metadata": {"colab": {"provenance": []},
                       "kernelspec": {"name": "python3", "display_name": "Python 3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 0}
    with open(OUT, "w") as f:
        json.dump(nb, f, indent=1)
    n_code = sum(1 for c in CELLS if c["cell_type"] == "code")
    print("wrote", os.path.relpath(OUT, REPO), f"({len(CELLS)} cells, {n_code} code)")


if __name__ == "__main__":
    main()
