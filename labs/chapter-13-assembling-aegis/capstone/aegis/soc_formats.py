"""
Real SOC data formats, and the adapters that ARE the integration.

  Wazuh  deeply nested JSON alerts        from_wazuh()  -> the alert shape every chapter expects
  Sigma  portable YAML detection rules    parse_sigma() -> title, level, tags, known false positives
  MISP   events with attributes           from_misp()   -> indicators with confidence and expiry

Two decisions in here are POLICY wearing the costume of parsing, and belong in
code review rather than in a prompt: what a Wazuh rule level means in a
four-value severity vocabulary, and whether a MISP indicator with to_ids=false
may ever trigger an action.
"""
import yaml

# ---------------------------------------------------------------- Wazuh

WAZUH_ALERT = {
    "timestamp": "2026-08-25T09:13:02.412+0000",
    "rule": {"level": 10, "description": "Multiple authentication failures followed by a success",
             "id": "5720", "mitre": {"id": ["T1110"], "tactic": ["Credential Access"], "technique": ["Brute Force"]},
             "groups": ["authentication_failures", "authentication_success"]},
    "agent": {"id": "017", "name": "fin-ws-042", "ip": "10.20.30.40"},
    "manager": {"name": "wazuh-manager-01"},
    "id": "1756112382.881232",
    "full_log": "Aug 25 09:13:02 fin-ws-042 sshd[4471]: Accepted password for j.okafor from 203.0.113.42 port 51234 ssh2",
    "data": {"srcip": "203.0.113.42", "srcuser": "j.okafor", "dstuser": "j.okafor"},
    "decoder": {"name": "sshd", "parent": "sshd"},
    "location": "/var/log/auth.log",
}

# Wazuh rule levels run 0-15. Mapping them to four words is a POLICY decision.
WAZUH_LEVEL_TO_SEVERITY = [(13, "critical"), (10, "high"), (7, "medium"), (0, "low")]


def wazuh_severity(level: int) -> str:
    for floor, severity in WAZUH_LEVEL_TO_SEVERITY:
        if level >= floor:
            return severity
    return "low"


def from_wazuh(alert: dict) -> dict:
    """Flatten a Wazuh alert into the shape every chapter already expects."""
    rule, data = alert.get("rule", {}), alert.get("data", {})
    return {
        "id": f"WZ-{alert.get('id', '?')}",
        "rule": rule.get("description", ""),
        "user": data.get("srcuser") or data.get("dstuser") or "",
        "src_ip": data.get("srcip", ""),
        "severity": wazuh_severity(int(rule.get("level", 0))),
        "severity_hint": wazuh_severity(int(rule.get("level", 0))),
        "asset": alert.get("agent", {}).get("name", ""),
        "mitre": rule.get("mitre", {}).get("id", []),
        "raw_log": alert.get("full_log", ""),
        "source": "wazuh",
    }

# ---------------------------------------------------------------- Sigma

SIGMA_RULE = """\
title: Multiple Failed Logins Followed by Success
id: 3f6a1c1e-7b8a-4c0b-9d2e-aegis000001
status: stable
description: Detects a burst of failed authentication attempts from one source followed by a successful login for the same account, a common brute-force or credential-stuffing pattern.
author: SOC detection engineering
level: high
tags:
  - attack.credential_access
  - attack.t1110
logsource:
  product: linux
  service: auth
detection:
  failures:
    event: auth_fail
  success:
    event: auth_success
  condition: failures | count() > 3 and success
falsepositives:
  - A user mistyping a password several times before succeeding
  - Password managers replaying stale credentials after a rotation
  - Automated jobs with an expired service credential
"""


def parse_sigma(text: str) -> dict:
    rule = yaml.safe_load(text)
    return {
        "id": rule.get("id"),
        "title": rule.get("title", ""),
        "description": rule.get("description", ""),
        "level": rule.get("level", "medium"),
        "tags": rule.get("tags", []),
        "known_false_positives": rule.get("falsepositives", []),
        "logsource": rule.get("logsource", {}),
    }


def routing_corpus_from_sigma(rules: list) -> dict:
    """Chapter 9 hand-wrote ROUTE_DESCRIPTIONS. A Sigma library already contains
    better descriptions - and the benign explanations - than anything you would invent."""
    corpus = {}
    for r in rules:
        route_id = r["title"].lower().replace(" ", "_")
        corpus[route_id] = (f"{r['title']}. {r['description']} Tags: {', '.join(r['tags'])}. "
                            f"Known benign causes: {'; '.join(r['known_false_positives'])}.")
    return corpus

# ---------------------------------------------------------------- MISP

MISP_EVENT = {
    "Event": {
        "id": "4417", "info": "Credential-stuffing infrastructure, August 2026",
        "threat_level_id": "2", "analysis": "2", "date": "2026-08-20",
        "Attribute": [
            {"type": "ip-dst", "category": "Network activity", "value": "203.0.113.42",
             "to_ids": True, "comment": "brute-force source, confirmed C2", "last_seen": "2026-08-24"},
            {"type": "ip-dst", "category": "Network activity", "value": "198.51.100.7",
             "to_ids": False, "comment": "reported by a partner, unconfirmed", "last_seen": "2026-03-02"},
            {"type": "domain", "category": "Network activity", "value": "it-support-reset.example",
             "to_ids": True, "comment": "phishing landing page", "last_seen": "2026-08-23"},
        ],
    }
}


def from_misp(event: dict) -> list:
    """Indicators with the two fields a toy dict cannot express: actionable (to_ids) and last_seen."""
    out = []
    for attr in event.get("Event", {}).get("Attribute", []):
        out.append({"value": attr["value"], "type": attr["type"], "category": attr.get("category"),
                    "actionable": bool(attr.get("to_ids", False)), "last_seen": attr.get("last_seen"),
                    "comment": attr.get("comment", "")})
    return out


def reputation_from_misp(indicators: list):
    """Build an ip_reputation(value) with the same signature Chapter 1 used, backed by
    MISP. Reported-but-not-actionable intel is a verdict of 'reported', never 'malicious'."""
    by_value = {i["value"]: i for i in indicators}

    def ip_reputation(value: str) -> dict:
        hit = by_value.get(value)
        if hit is None:
            return {"ip": value, "verdict": "unknown", "actionable": False, "score": 0}
        return {"ip": value,
                "verdict": "malicious" if hit["actionable"] else "reported",
                "actionable": hit["actionable"],
                "score": 90 if hit["actionable"] else 40,
                "last_seen": hit["last_seen"], "comment": hit["comment"]}
    return ip_reputation
