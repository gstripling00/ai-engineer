"""
The core pipeline: chunk -> embed -> retrieve -> ground.

Everything here is offline and deterministic. The embedder is term-frequency
plus cosine — weaker than a trained model (it matches words, not meaning) but
it demonstrates the chunking effect faithfully and runs in CI. Same interface
as a real embedder, so swapping one in is a body swap, not a rewrite.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field

# ---------------------------------------------------------------- chunking


def _sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


sentences = _sentences


def chunk_fixed(text: str, size: int = 120, overlap: int = 20) -> list:
    """Cut every `size` characters. Simple, and blind: it splits sentences, words,
    and runbook steps straight down the middle."""
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += size - overlap
    return chunks


def chunk_sentence_window(text: str, window: int = 1) -> list:
    """One chunk per sentence PLUS `window` neighbours on each side. The target
    sentence stays precise for matching; the window restores context."""
    sents = _sentences(text)
    out = []
    for i in range(len(sents)):
        lo, hi = max(0, i - window), min(len(sents), i + window + 1)
        out.append(" ".join(sents[lo:hi]))
    return out


def chunk_semantic(text: str, group: int = 2) -> list:
    """Group consecutive sentences so a coherent unit stays together."""
    sents = _sentences(text)
    return [" ".join(sents[i:i + group]) for i in range(0, len(sents), group)]


def chunk_hierarchical(text: str, child_sents: int = 1, parent_sents: int = 4) -> list:
    """Index small children, return the parent section they belong to."""
    sents = _sentences(text)
    parents = [" ".join(sents[i:i + parent_sents]) for i in range(0, len(sents), parent_sents)]
    out, seen = [], set()
    for i in range(0, len(sents), child_sents):
        parent = parents[min(i // parent_sents, len(parents) - 1)]
        if parent not in seen:
            seen.add(parent)
            out.append(parent)
    return out


def chunk_by_step(text: str) -> list:
    """Structure-aware: split a runbook on its own 'Step N:' boundaries."""
    parts = re.split(r"(?=Step\s+\d+\s*:)", text)
    return [p.strip() for p in parts if p.strip()]


STRATEGIES = {
    "fixed": chunk_fixed,
    "sentence-window": chunk_sentence_window,
    "semantic": chunk_semantic,
    "hierarchical": chunk_hierarchical,
}

# ---------------------------------------------------------------- embedding


def tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def embed(text: str) -> Counter:
    """Term-frequency vector. Stand-in for a trained embedding model."""
    return Counter(tokens(text))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0

# ---------------------------------------------------------------- index


@dataclass
class Chunk:
    doc_id: str
    text: str
    vec: Counter
    meta: dict = field(default_factory=dict)


class VectorIndex:
    """Chunk every document, embed every chunk, keep them. Retrieval embeds the
    query and returns the nearest chunks. That is the whole of a vector database,
    conceptually; the real ones add persistence, scale, filtering, and speed."""

    def __init__(self):
        self.chunks: list[Chunk] = []

    def index(self, docs: dict, strategy: str = "semantic", metadata: dict | None = None):
        self.chunks.clear()
        chunker = STRATEGIES[strategy]
        for doc_id, text in docs.items():
            for piece in chunker(text):
                self.chunks.append(Chunk(doc_id, piece, embed(piece),
                                         dict((metadata or {}).get(doc_id, {}))))
        return self

    def retrieve(self, query: str, k: int = 3, where: dict | None = None) -> list:
        """Return [(score, Chunk)] best-first. `where` filters on metadata."""
        qv = embed(query)
        pool = [c for c in self.chunks
                if not where or all(c.meta.get(key) == val for key, val in where.items())]
        scored = [(cosine(qv, c.vec), c) for c in pool]
        scored = [(s, c) for s, c in scored if s > 0]        # a score of zero is not a hit
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

# ---------------------------------------------------------------- comparison


def evaluate_strategies(docs: dict, query: str, expected_doc: str) -> dict:
    """Index the corpus once per strategy; report top doc, score, and correctness."""
    results = {}
    for name in STRATEGIES:
        idx = VectorIndex().index(docs, name)
        top = idx.retrieve(query, k=1)
        top_doc = top[0][1].doc_id if top else None
        results[name] = {"top_doc": top_doc,
                         "score": round(top[0][0], 3) if top else 0.0,
                         "correct": top_doc == expected_doc}
    return results
