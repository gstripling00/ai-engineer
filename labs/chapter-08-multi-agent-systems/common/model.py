"""
The model seam. get_model() reads AEGIS_MODEL: 'mock' is deterministic and free;
'openai' calls the chat completions API over urllib (stdlib only) when
OPENAI_API_KEY is set, and falls back to mock with a note when it is not.

Workers use the model for one thing: turning structured findings into the
one-paragraph ticket summary a human reads. Every decision that matters
(true positive? malicious? may this role call this tool?) is made in code.
"""
import json
import os
import urllib.request


class MockModel:
    name = "mock"

    def summarize(self, findings: dict) -> str:
        ev = findings.get("evidence", {})
        return (f"{findings.get('verdict', 'unknown')} for {findings['alert']['user']} "
                f"from {findings['alert']['src_ip']}: ip_verdict={ev.get('ip_verdict')}, "
                f"egress_observed={ev.get('egress_observed')}.")


class OpenAIModel:
    name = "openai"
    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        self.api_key, self.model = api_key, model

    def summarize(self, findings: dict) -> str:
        body = json.dumps({"model": self.model, "messages": [
            {"role": "system", "content": "Summarise these SOC findings in one sentence for a ticket."},
            {"role": "user", "content": json.dumps(findings, default=str)}]}).encode()
        req = urllib.request.Request(self.URL, data=body, method="POST",
                                     headers={"Authorization": f"Bearer {self.api_key}",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)["choices"][0]["message"]["content"].strip()


def get_model():
    tier = os.environ.get("AEGIS_MODEL", "mock")
    key = os.environ.get("OPENAI_API_KEY", "")
    if tier == "openai" and key:
        return OpenAIModel(key)
    if tier == "openai":
        print("AEGIS_MODEL=openai but OPENAI_API_KEY is not set - using mock")
    return MockModel()
