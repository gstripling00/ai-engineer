"""
The SOC tools themselves — the *callables* that all three mechanisms in this
chapter wire up. Function calling, OpenAPI, and MCP differ in how a tool is
described and discovered, not in what it does, so the implementations live here
once and every mechanism imports them.

Data is small, fixed, and offline: the same alert Chapters 1 and 2 used.
"""
import json

REPUTATION = {
    "203.0.113.42": {"score": 92, "verdict": "malicious",
                     "categories": ["bruteforce", "c2"], "last_seen": "2026-03-01"},
}

LOGS = [
    {"ts": "09:12:04", "event": "auth_fail",    "user": "a.singh",  "src_ip": "203.0.113.42"},
    {"ts": "09:12:31", "event": "auth_fail",    "user": "a.singh",  "src_ip": "203.0.113.42"},
    {"ts": "09:13:02", "event": "auth_success", "user": "a.singh",  "src_ip": "203.0.113.42"},
    {"ts": "09:40:17", "event": "auth_success", "user": "j.okafor", "src_ip": "10.20.30.40"},
]

USERS = {
    "a.singh":  {"role": "SRE",             "dept": "Platform", "privileged": True},
    "j.okafor": {"role": "Finance Analyst", "dept": "Finance",  "privileged": False},
}

ALERT = {"id": "ALERT-7750", "rule": "Multiple failed logins followed by success",
         "user": "a.singh", "src_ip": "203.0.113.42", "severity_hint": "high"}


def ip_reputation(ip: str) -> str:
    """Look up threat-intel reputation for an IP address."""
    rep = REPUTATION.get(ip, {"score": 0, "verdict": "unknown", "categories": []})
    return json.dumps({"ip": ip, **rep})


def search_logs(query: str, window: str = "1h") -> str:
    """Search SIEM logs by event type or username."""
    q = query.lower()
    hits = [entry for entry in LOGS
            if q in entry["event"].lower() or q in entry.get("user", "").lower()]
    return json.dumps({"query": query, "window": window, "count": len(hits), "results": hits})


def user_context(user: str) -> str:
    """Fetch an account's role, department, and privilege level."""
    info = USERS.get(user, {"role": "unknown", "dept": "unknown", "privileged": False})
    return json.dumps({"user": user, **info})


# name -> callable. Every mechanism's registry is a view of this table.
TOOLS = {
    "ip_reputation": ip_reputation,
    "search_logs": search_logs,
    "user_context": user_context,
}
