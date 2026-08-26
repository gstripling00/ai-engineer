"""
The analyst interface. Aegis is headless: it writes into the panes analysts
already use. Everything it emits is an interface contract, and if a surface
needs a field the agent does not emit, that is an OBSERVABILITY bug, not a UI bug.
"""

REQUIRED_FIELDS = ["trace_id", "verdict", "severity", "escalated", "escalation_reasons",
                   "evidence", "open_questions", "ticket", "audit", "trace"]


def interface_contract(findings: dict) -> dict:
    """Can the interface show what a human needs? Name what is missing."""
    missing = [f for f in REQUIRED_FIELDS if f not in findings or findings[f] is None]
    return {"satisfied": not missing, "missing": missing}


def render_ticket_comment(findings: dict, trace: list | None = None) -> str:
    """The comment Aegis posts on the ticket. Plain text, because ticket systems are."""
    ev = findings.get("evidence", {})
    lines = [
        f"AEGIS triage - trace {findings.get('trace_id', '?')} - model tier: {findings.get('model_tier', '?')}",
        "",
        f"Verdict:   {findings.get('verdict', '?')}",
        f"Severity:  {findings.get('severity', '?')}",
        f"Escalated: {findings.get('escalated')}" + (
            f"  ({'; '.join(findings.get('escalation_reasons', []))})" if findings.get("escalated") else ""),
        "",
        "Evidence:",
    ]
    lines += [f"  - {k}: {v}" for k, v in ev.items()]
    if findings.get("injection_detected"):
        lines += ["", "WARNING: the source log contained an instruction aimed at the agent.",
                  "It was neutralised and did not influence this verdict."]
    if findings.get("open_questions"):
        lines += ["", "Open questions for the analyst:"] + [f"  - {q}" for q in findings["open_questions"]]
    if trace:
        lines += ["", "Stages:"] + [f"  {s['stage']}" for s in trace]
    denied = [e for e in findings.get("audit", []) if not e["allowed"]]
    lines += ["", f"Tool calls: {len(findings.get('audit', []))} ({len(denied)} denied - on the record)"]
    return "\n".join(lines)
