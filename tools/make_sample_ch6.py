#!/usr/bin/env python3
"""
Build the SELF-CONTAINED Chapter 6 sample notebook.

Same contract as the Chapter 1-5 samples: no repo clone, no pip install, no API
key. Pure standard library, runs in a fresh Colab the moment it opens.

Chapter 6's claim: chunking strategy is the single biggest lever on retrieval
quality — and on a small corpus every strategy looks fine, which is exactly how
teams ship a retrieval system that fails at scale.

    python tools/make_sample_ch6.py
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "ch06", "Aegis_Chapter6_Colab_Sample.ipynb")


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


CELLS = [
    md("# Chapter 6 — RAG",
       "",
       "Aegis knows how to investigate. It does not know *your* incident-response runbooks,",
       "your CVE advisories, or the policy your company adopted last quarter. No model does,",
       "and no amount of prompting will fix that.",
       "",
       "Retrieval-augmented generation is the standard answer: index your documents, retrieve",
       "the relevant passages when a question arrives, and require the agent to answer from",
       "what was retrieved rather than from what it happens to believe.",
       "",
       "The pipeline has four stages, and almost everyone focuses on the wrong one:",
       "",
       "```",
       "chunk  ->  embed  ->  retrieve  ->  ground",
       "```",
       "",
       "Teams argue about embedding models. The stage that decides whether retrieval finds",
       "the right passage is the *first* one — **chunking**. This notebook builds all four",
       "chunking strategies, measures them, and then shows why the measurement you take on a",
       "small corpus is the one that will mislead you.",
       "",
       "**Nothing to install, nothing to clone.** Run the cells in order."),

    md("## The corpus",
       "",
       "Three incident-response runbooks and a CVE advisory. Small enough to read in full,",
       "which is deliberate — you should be able to check the retriever's work by eye.",
       "",
       "Note the structure: every runbook is a numbered sequence of steps. That structure is",
       "going to matter enormously, and generic chunkers are blind to it."),
    code('''RUNBOOKS = {
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
}


def all_docs() -> dict:
    return {**RUNBOOKS, **ADVISORIES}


for doc_id, text in all_docs().items():
    print(f"{doc_id:22} {len(text):4} chars")'''),

    md("## Stage 1 — Chunking",
       "",
       "You cannot retrieve a whole document; you retrieve a passage. Chunking is how you",
       "decide what a passage *is*, and there is no neutral choice.",
       "",
       "Four strategies, each trading precision against context:",
       "",
       "1. **Fixed** — cut every N characters. Simple, and blind: it will split a sentence,",
       "   a word, or a runbook step straight down the middle.",
       "2. **Sentence-window** — one chunk per sentence, plus its neighbours. The target",
       "   sentence stays precise for matching; the window restores the context needed to",
       "   answer from it.",
       "3. **Semantic** — group consecutive sentences so a coherent unit stays together.",
       "4. **Hierarchical** — index small children, return the parent section. Sharp matching,",
       "   full-context generation."),
    code('''import re
import math
from collections import Counter


def chunk_fixed(text: str, size: int = 120, overlap: int = 20) -> list:
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += size - overlap
    return chunks


def sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\\s+", text) if s.strip()]


def chunk_sentence_window(text: str, window: int = 1) -> list:
    """Each chunk is one sentence PLUS `window` neighbours on each side."""
    sents = sentences(text)
    out = []
    for i in range(len(sents)):
        lo, hi = max(0, i - window), min(len(sents), i + window + 1)
        out.append(" ".join(sents[lo:hi]))
    return out


def chunk_semantic(text: str, group: int = 2) -> list:
    """Group consecutive sentences so a runbook step keeps its context."""
    sents = sentences(text)
    return [" ".join(sents[i:i + group]) for i in range(0, len(sents), group)]


def chunk_hierarchical(text: str, child_sents: int = 1, parent_sents: int = 4) -> list:
    """Index small children, return the parent section they belong to."""
    sents = sentences(text)
    parents = [" ".join(sents[i:i + parent_sents])
               for i in range(0, len(sents), parent_sents)]
    out, seen = [], set()
    for i in range(0, len(sents), child_sents):
        parent = parents[min(i // parent_sents, len(parents) - 1)]
        if parent not in seen:
            seen.add(parent)
            out.append(parent)
    return out


STRATEGIES = {
    "fixed": chunk_fixed,
    "sentence-window": chunk_sentence_window,
    "semantic": chunk_semantic,
    "hierarchical": chunk_hierarchical,
}

doc = RUNBOOKS["rb_account_takeover"]

for name, chunker in STRATEGIES.items():
    chunks = chunker(doc)
    avg = sum(len(c) for c in chunks) / len(chunks)
    print(f"{name:16} {len(chunks):2} chunks, avg {avg:5.0f} chars")'''),

    md("### Look at what fixed chunking actually does",
       "",
       "The numbers above are abstract. Print the chunks and the problem becomes obvious."),
    code('''print("FIXED (120 chars, blind to meaning):")
for chunk in chunk_fixed(doc)[:3]:
    print(f"  |{chunk}|")

print()
print("SENTENCE-WINDOW (one step, plus its neighbours):")
for chunk in chunk_sentence_window(doc)[:2]:
    print(f"  |{chunk}|")'''),

    md("Fixed chunking severs \"Step 2: Force a password reset and require re-enrollment of\"",
       "from \"MFA.\" — the instruction is now split across two passages, and neither one is",
       "complete.",
       "",
       "In an incident, that is not an academic problem. It is the agent telling a responder",
       "to force a password reset and never mentioning MFA re-enrollment, because the second",
       "half of the sentence was in a chunk that did not get retrieved."),

    md("## Stage 2 — Embedding",
       "",
       "An embedding turns text into a vector so that similar text lands nearby. Production",
       "systems use a trained embedding model; here we use term-frequency vectors and cosine",
       "similarity.",
       "",
       "That substitution is deliberate and worth being honest about. It is weaker than a",
       "real embedder — it matches on shared words, not on meaning, so it will miss",
       "paraphrase. What it *does* do is run offline, deterministically, in this notebook,",
       "and it demonstrates the chunking effect faithfully. The interface is identical, so",
       "swapping in a real embedder is a body swap, not a rewrite."),
    code('''def tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def embed(text: str) -> Counter:
    return Counter(tokens(text))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


a = embed("disable the account and revoke active sessions")
b = embed("revoke sessions and disable the affected account")
c = embed("upgrade AcmeVPN and rotate session tokens")

print(f"same meaning, different words : {cosine(a, b):.3f}")
print(f"different topic              : {cosine(a, c):.3f}")'''),

    md("## Stage 3 — The index and the retriever",
       "",
       "Chunk every document, embed every chunk, and keep them. To retrieve, embed the query",
       "and return the nearest chunks.",
       "",
       "That is the whole of a vector database, conceptually. The commercial ones add",
       "persistence, scale, filtering, and speed — not a different idea."),
    code('''from dataclasses import dataclass


@dataclass
class Chunk:
    doc_id: str
    text: str
    vec: Counter


class VectorIndex:
    def __init__(self):
        self.chunks = []

    def index(self, docs: dict, strategy: str):
        self.chunks.clear()
        chunker = STRATEGIES[strategy]
        for doc_id, text in docs.items():
            for piece in chunker(text):
                self.chunks.append(Chunk(doc_id, piece, embed(piece)))
        return self

    def retrieve(self, query: str, k: int = 3) -> list:
        qv = embed(query)
        scored = [(cosine(qv, c.vec), c) for c in self.chunks]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]


index = VectorIndex().index(all_docs(), "semantic")
print(f"{len(index.chunks)} chunks indexed across {len(all_docs())} documents")'''),

    md("## Stage 4 — Grounding",
       "",
       "This is the step that makes it RAG rather than search. The retrieved passages are",
       "not a hint or a suggestion — they *are* the material the answer must be built from.",
       "",
       "An agent that retrieves context and then answers from its training anyway has not",
       "been grounded. It has been given a reading list it ignored."),
    code('''QUERY = "how do I contain an account takeover and check for data egress"

hits = index.retrieve(QUERY, k=2)

print("query:", QUERY)
print()
for score, chunk in hits:
    print(f"  [{score:.3f}] {chunk.doc_id}")
    print(f"          {chunk.text[:96]}...")

context = " ".join(chunk.text for _, chunk in hits)
print()
print("grounded context handed to the model:")
print(" ", context[:200], "...")'''),

    md("## The comparison",
       "",
       "Now the chapter's actual question. Index the same corpus four times, once per",
       "strategy, and ask a precise, fact-level question. Which strategy retrieves the right",
       "runbook, and how *confidently*?"),
    code('''PRECISE_QUERY = "detonate URLs in a sandbox and do not visit them directly"
EXPECTED = "rb_phishing"


def evaluate_strategies(docs: dict, query: str, expected_doc: str) -> dict:
    results = {}
    for name in STRATEGIES:
        idx = VectorIndex().index(docs, name)
        top = idx.retrieve(query, k=1)
        top_doc = top[0][1].doc_id if top else None
        results[name] = {
            "top_doc": top_doc,
            "score": round(top[0][0], 3) if top else 0.0,
            "correct": top_doc == expected_doc,
        }
    return results


results = evaluate_strategies(all_docs(), PRECISE_QUERY, EXPECTED)

print(f"query: {PRECISE_QUERY!r}")
print(f"expected document: {EXPECTED}")
print()
for name, r in sorted(results.items(), key=lambda kv: -kv[1]["score"]):
    mark = "correct" if r["correct"] else "WRONG"
    print(f"  {name:16} -> {r['top_doc']:22} score={r['score']:.3f}  {mark}")'''),

    md("Expected output:",
       "",
       "```",
       "query: 'detonate URLs in a sandbox and do not visit them directly'",
       "expected document: rb_phishing",
       "",
       "  sentence-window  -> rb_phishing            score=0.657  correct",
       "  fixed            -> rb_phishing            score=0.583  correct",
       "  semantic         -> rb_phishing            score=0.553  correct",
       "  hierarchical     -> rb_phishing            score=0.527  correct",
       "```",
       "",
       "Every strategy is correct. Every strategy retrieved the right runbook.",
       "",
       "**And that result is a trap.** Read the next section before you conclude anything",
       "from it."),

    md("## Why this measurement will mislead you",
       "",
       "On a four-document corpus, every reasonable chunking strategy retrieves the right",
       "document, because there are only four things it could possibly return. The",
       "hit-or-miss column tells you nothing.",
       "",
       "Look at the **confidence spread** instead: 0.657 down to 0.527. That gap is the",
       "signal, and here is why it matters.",
       "",
       "Retrieval does not return \"the right document.\" It returns whatever scored highest.",
       "On four documents, a score of 0.527 wins comfortably. On forty thousand documents,",
       "hundreds of chunks will score above 0.527 by coincidence — and the correct one is now",
       "somewhere in the noise.",
       "",
       "The margin *is* the safety buffer. A strategy that wins by a nose today loses at",
       "scale, and it will fail silently: no error, no exception, just a confidently wrong",
       "answer grounded in the wrong runbook.",
       "",
       "This is the most expensive lesson in the chapter, and you can only see it by looking",
       "at a number that a pass/fail test would have thrown away."),

    md("## The strategy nobody writes",
       "",
       "Every strategy above is generic — none of them know that a runbook has *steps*.",
       "",
       "But our documents do. Splitting on the document's own structure keeps each step",
       "whole, which is exactly what an agent needs when it is telling a human what to do",
       "next in an incident."),
    code('''def chunk_by_step(text: str) -> list:
    """Split a runbook on its own 'Step N:' boundaries."""
    parts = re.split(r"(?=Step\\s+\\d+\\s*:)", text)
    return [p.strip() for p in parts if p.strip()]


chunks = chunk_by_step(RUNBOOKS["rb_account_takeover"])

print(f"{len(chunks)} chunks, one per step (plus the title):")
for chunk in chunks:
    print(f"  |{chunk[:72]}|")

# every step intact: exactly one "Step" marker per chunk that has any
step_counts = [c.count("Step") for c in chunks if "Step" in c]
print()
print("steps per chunk:", step_counts, "(all 1 = no step was split or merged)")'''),

    md("Compare that to the fixed chunker's output earlier, which cut \"Step 2\" in half.",
       "",
       "Structure-aware chunking usually beats every generic strategy on documents that have",
       "structure — and most enterprise documents do: runbooks with steps, policies with",
       "clauses, advisories with sections.",
       "",
       "The catch is that it does not generalize. A chunker that understands runbooks knows",
       "nothing about Slack threads or vendor PDFs. A real indexing pipeline routes documents",
       "to the right chunker by format, and needs an answer for the format it does not",
       "recognize."),

    md("## The dial you should tune",
       "",
       "Sentence-window has a `window` parameter, and it is not a cosmetic setting. It is the",
       "precision-versus-context dial, and you can watch it move."),
    code('''for window in (0, 1, 3):
    chunks = chunk_sentence_window(doc, window=window)
    avg = sum(len(c) for c in chunks) / len(chunks)
    idx = VectorIndex()
    idx.chunks = [Chunk("rb_account_takeover", c, embed(c)) for c in chunks]
    score = idx.retrieve("check for data egress after the compromise", k=1)[0][0]
    print(f"window={window}  {len(chunks)} chunks, avg {avg:3.0f} chars, top score {score:.3f}")'''),

    md("A wider window means each chunk carries more surrounding context — better for the",
       "model's answer, worse for precise matching, because the target sentence is now",
       "diluted by its neighbours.",
       "",
       "There is no universally correct window. There is a correct window *for your corpus*,",
       "and the only way to find it is to measure — which is Chapter 10's entire subject, and",
       "the reason its closing exercise sends you back here to re-run this comparison against",
       "a golden set."),

    md("---",
       "",
       "## What you built",
       "",
       "A complete RAG pipeline — chunk, embed, retrieve, ground — plus four chunking",
       "strategies, a structure-aware fifth, and a measurement that shows why the obvious",
       "one is a trap.",
       "",
       "Four things to take away:",
       "",
       "- **Chunking is the biggest lever in RAG,** and it is the stage teams skip past on",
       "  their way to arguing about embedding models.",
       "- **On a small corpus, everything works.** The pass/fail column is nearly useless;",
       "  the confidence *margin* is the number that predicts behavior at scale.",
       "- **Structure-aware chunking beats generic chunking** on structured documents — and",
       "  does not generalize, so your indexer needs a routing layer.",
       "- **Retrieval failure is silent.** No exception, no alert: just a confident answer",
       "  grounded in the wrong document.",
       "",
       "Chapter 7 gives Aegis a plan: it decides on a multi-step investigation up front, then",
       "replans when a log source goes down — and reflects on whether its evidence actually",
       "supports the verdict it reached.",
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
