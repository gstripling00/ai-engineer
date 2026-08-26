"""
The corpus: three incident-response runbooks and two CVE advisories.

Small enough to read in full, which is deliberate — you should be able to check
the retriever's work by eye. Every runbook is a numbered sequence of steps; that
structure matters, and generic chunkers are blind to it.

GOLDEN_SET is a handful of (query, expected document) pairs. It is what turns
"it seems to work" into a number — the bridge to Chapter 10.
"""

RUNBOOKS = {
    "rb_account_takeover": (
        "Runbook: Account Takeover Response. "
        "Step 1: Immediately disable the affected account and revoke active sessions. "
        "Step 2: Force a password reset and require re-enrollment of MFA. "
        "Step 3: Review authentication logs for the blast radius and lateral movement. "
        "Step 4: Check for data egress from the account in the 24 hours before and after the compromise. "
        "Step 5: If egress is confirmed, escalate to the incident commander and open a Sev-1."
    ),
    "rb_phishing": (
        "Runbook: Phishing Report Handling. "
        "Step 1: Preserve the reported email and extract sender, URLs, and headers. "
        "Step 2: Detonate URLs in a sandbox; do not visit them directly. "
        "Step 3: Search mail logs for other recipients of the same campaign. "
        "Step 4: Block the sender domain and the malicious URLs at the gateway. "
        "Step 5: Notify recipients who clicked and force password resets for any who entered credentials."
    ),
    "rb_data_egress": (
        "Runbook: Suspected Data Exfiltration. "
        "Step 1: Identify the destination IP and volume of the transfer. "
        "Step 2: Check the destination against threat intelligence. "
        "Step 3: If the destination is malicious, block it at the firewall immediately. "
        "Step 4: Determine what data classification was involved and notify data protection. "
        "Step 5: Preserve netflow and endpoint evidence for forensics."
    ),
}

ADVISORIES = {
    "cve_2026_1000": (
        "Advisory CVE-2026-1000: Critical authentication bypass in AcmeVPN below 4.2. "
        "Remote attackers can bypass MFA by replaying a captured session token. "
        "Mitigation: upgrade to 4.2, rotate all session tokens, and invalidate long-lived sessions."
    ),
    "cve_2026_2000": (
        "Advisory CVE-2026-2000: High severity path traversal in AcmeVPN admin console. "
        "Remote attackers can read configuration files without authentication. "
        "Mitigation: apply the vendor patch and rotate stored credentials."
    ),
}

# document id -> metadata. Real corpora carry this from the source system.
METADATA = {
    "rb_account_takeover": {"type": "runbook", "owner": "soc", "severity": "high"},
    "rb_phishing":         {"type": "runbook", "owner": "soc", "severity": "medium"},
    "rb_data_egress":      {"type": "runbook", "owner": "soc", "severity": "high"},
    "cve_2026_1000":       {"type": "advisory", "owner": "vuln-mgmt", "severity": "critical"},
    "cve_2026_2000":       {"type": "advisory", "owner": "vuln-mgmt", "severity": "high"},
}

# (query, expected document). Deliberately mixed: precise, vague, and identifier-shaped.
GOLDEN_SET = [
    ("detonate URLs in a sandbox and do not visit them directly", "rb_phishing"),
    ("how do I contain an account takeover", "rb_account_takeover"),
    ("check for data egress after the compromise", "rb_account_takeover"),
    ("block a malicious destination at the firewall", "rb_data_egress"),
    ("notify data protection about the classification involved", "rb_data_egress"),
    ("MFA bypass by replaying a session token", "cve_2026_1000"),
    ("CVE-2026-2000 mitigation", "cve_2026_2000"),
    ("someone hacked us", "rb_account_takeover"),
]


def all_docs() -> dict:
    return {**RUNBOOKS, **ADVISORIES}
