"""The SOC world: fixed data, four tools, and the one thing that changes the world."""
import json

SEED_ALERT = {"id": "ALERT-7731", "rule": "Multiple failed logins followed by success",
              "user": "j.okafor", "src_ip": "203.0.113.42", "severity_hint": "high"}

LOGS = [
    {"ts": "09:12:04", "event": "auth_fail",     "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:12:19", "event": "auth_fail",     "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:13:02", "event": "auth_success",  "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:14:10", "event": "file_download", "user": "j.okafor", "bytes": 48_000_000},
]

REPUTATION = {"203.0.113.42": {"score": 92, "verdict": "malicious", "categories": ["bruteforce", "c2"]}}
DIRECTORY = {"j.okafor": {"role": "Finance Analyst", "privileged": False},
             "a.singh":  {"role": "SRE",             "privileged": True}}

TICKETS: list = []


def reset_tickets() -> None:
    TICKETS.clear()


def search_logs(query: str, window: str = "1h") -> str:
    q = query.lower()
    hits = [e for e in LOGS if q in e["event"].lower() or q in e.get("user", "").lower()]
    return json.dumps({"count": len(hits), "window": window, "results": hits})


def ip_reputation(ip: str) -> str:
    rep = REPUTATION.get(ip, {"score": 0, "verdict": "unknown", "categories": []})
    return json.dumps({"ip": ip, **rep})


def get_user_context(user: str) -> str:
    return json.dumps({"user": user, **DIRECTORY.get(user, {"role": "unknown", "privileged": False})})


def create_ticket(title: str, severity: str, summary: str) -> str:
    """The ONLY tool here that changes the world."""
    ticket = {"id": f"INC-{1000 + len(TICKETS) + 1}", "title": title,
              "severity": severity, "summary": summary, "status": "open"}
    TICKETS.append(ticket)
    return json.dumps(ticket)


TOOLS = {"search_logs": search_logs, "ip_reputation": ip_reputation,
         "get_user_context": get_user_context, "create_ticket": create_ticket}
WORLD_CHANGING = {"create_ticket"}
