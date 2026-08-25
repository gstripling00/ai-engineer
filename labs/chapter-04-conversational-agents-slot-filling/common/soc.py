"""
Fixed SOC fixtures used by the lab. Offline and deterministic on purpose: every
cell in the notebook produces the same output on every run.
"""

# The employee's opening message. Unusually complete — which is exactly the case
# where a naive bot embarrasses itself by asking all five questions anyway.
PHISHING_REPORT = (
    "Hi security team, I got a weird email this morning claiming to be from IT "
    "asking me to reset my password at hxxp://it-support-reset[.]example. I did "
    "NOT click it. Sender was helpdesk@it-support-reset.example. Around 8:40am."
)

# A vaguer report: the extractor fills one slot and the agent must ask for the rest.
VAGUE_REPORT = "I think I got a phishing email this morning"

# The alert Chapters 1-3 triaged, kept here so later chapters share one fixture.
SEED_ALERT = {
    "id": "ALERT-7750",
    "rule": "Multiple failed logins followed by success",
    "user": "a.singh",
    "src_ip": "203.0.113.42",
    "severity_hint": "high",
}
