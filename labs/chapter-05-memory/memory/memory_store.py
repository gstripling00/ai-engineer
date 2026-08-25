"""
Episodic, semantic, and procedural memory (§5.3-§5.5).

  EpisodicMemory    past incidents, recalled by similarity above a THRESHOLD.
                    Similarity here is Jaccard token overlap; production uses
                    embeddings and cosine. Same interface, body swap.
  SEMANTIC_FACTS    durable facts about the enterprise — what is TRUE, not what
                    happened. A threat-intel feed and a directory in production.
  ProceduralMemory  what worked. A cache with a quality gate: only successes
                    teach, and a proven playbook is not displaced by a weaker one.

assess_with_memory() puts them together. Recall happens BEFORE record; get that
backwards and every incident matches itself.
"""
import json
import time
from dataclasses import dataclass, field


def tokens(text: str) -> set:
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
    return {t for t in cleaned.split() if len(t) > 2}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)          # Jaccard; stands in for cosine


@dataclass
class EpisodicMemory:
    episodes: list = field(default_factory=list)

    def record(self, incident: dict) -> None:
        self.episodes.append({"ts": time.time(),
                              "incident": incident,
                              "key": json.dumps(incident, sort_keys=True)})

    def recall(self, query: str, k: int = 3, threshold: float = 0.2) -> list:
        scored = [(similarity(query, e["key"]), e) for e in self.episodes]
        scored = [(s, e) for s, e in scored if s >= threshold]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": round(s, 3), **e["incident"]} for s, e in scored[:k]]


SEMANTIC_FACTS = {
    "known_bad_senders": ["helpdesk@it-support-reset.example"],
    "asset_owners": {"j.okafor": "Finance", "a.singh": "Platform/SRE"},
    "privileged_accounts": ["a.singh"],
}


def is_known_bad_sender(sender: str) -> bool:
    return sender in SEMANTIC_FACTS["known_bad_senders"]


@dataclass
class ProceduralMemory:
    playbooks: dict = field(default_factory=dict)   # category -> {steps, successes}

    def learn(self, category: str, steps: list, succeeded: bool) -> None:
        if not succeeded:
            return                                   # failures do not teach
        entry = self.playbooks.get(category)
        if entry and entry["steps"] == list(steps):
            entry["successes"] += 1
        elif not entry or entry["successes"] == 0:
            self.playbooks[category] = {"steps": list(steps), "successes": 1}
        # a different, weaker sequence never overwrites a proven one

    def recall(self, category: str):
        return self.playbooks.get(category)


def assess_with_memory(incident: dict,
                       episodic: EpisodicMemory,
                       procedural: ProceduralMemory | None = None) -> dict:
    query = f"{incident.get('category', '')} {incident.get('sender', '')}"

    prior = episodic.recall(query)                       # RECALL first
    same_sender = [p for p in prior if p.get("sender") == incident.get("sender")]
    is_campaign = len(same_sender) >= 2                  # this one makes three

    playbook = procedural.recall(incident.get("category", "")) if procedural else None

    return {
        "incident": incident,
        "related_prior": prior,
        "is_campaign": is_campaign,
        "known_bad_sender": is_known_bad_sender(incident.get("sender", "")),
        "recommended_severity": "high" if is_campaign else "medium",
        "playbook": playbook,
    }
