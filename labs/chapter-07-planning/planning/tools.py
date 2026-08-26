"""The SOC tools and fixed data the planner investigates with. Offline and deterministic."""
import json

LOGS = [
    {"ts": "09:12:04", "event": "auth_fail",    "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:12:19", "event": "auth_fail",    "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:12:41", "event": "auth_fail",    "user": "j.okafor", "src_ip": "203.0.113.42"},
    {"ts": "09:13:02", "event": "auth_success", "user": "j.okafor", "src_ip": "203.0.113.42"},
]

REPUTATION = {
    "203.0.113.42": {"score": 92, "verdict": "malicious", "categories": ["bruteforce", "c2"]},
}

DIRECTORY = {
    "j.okafor": {"role": "Finance Analyst", "privileged": False},
    "a.singh":  {"role": "SRE",             "privileged": True},
}

INCIDENT = {"id": "INC-7", "category": "brute_force", "user": "j.okafor", "src_ip": "203.0.113.42"}


def search_logs(query: str, window: str = "1h") -> str:
    q = query.lower()
    hits = [e for e in LOGS if q in e["event"].lower() or q in e.get("user", "").lower()]
    return json.dumps({"count": len(hits), "window": window, "results": hits})


def ip_reputation(ip: str) -> str:
    rep = REPUTATION.get(ip, {"score": 0, "verdict": "unknown", "categories": []})
    return json.dumps({"ip": ip, **rep})


def get_user_context(user: str) -> str:
    return json.dumps({"user": user, **DIRECTORY.get(user, {"role": "unknown", "privileged": False})})


TOOLS = {"search_logs": search_logs,
         "ip_reputation": ip_reputation,
         "get_user_context": get_user_context}

# What each tool is FOR, in the words a goal would use. select_tool() matches
# against these descriptions; the model sees the same prose in a real system.
TOOL_DESCRIPTIONS = {
    "search_logs":      "search the SIEM logs for events, auth failures, and login history",
    "ip_reputation":    "check whether an ip address is malicious using threat intelligence reputation",
    "get_user_context": "look up an account's identity, role, department, and whether it is privileged",
}


def call_tool(name: str, args: dict) -> str:
    fn = TOOLS.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    return fn(**args)
