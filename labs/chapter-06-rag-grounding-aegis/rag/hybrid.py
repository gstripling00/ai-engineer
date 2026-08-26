"""
Query transformation and hybrid retrieval.

Dense embeddings capture meaning and are bad at exact tokens: identifiers,
error codes, CVE numbers. BM25 (sparse, lexical) is the opposite. They fail
differently, which is the whole argument for running both.
"""
import re

from rank_bm25 import BM25Okapi

from .pipeline import tokens

# ---------------------------------------------------------------- query rewriting

# user vocabulary -> document vocabulary. A real system asks a model to do this;
# the table makes the effect visible and deterministic.
REWRITES = [
    (r"\b(account (got |was |is )?)?(taken over|took over|takeover|hijacked)\b", "account takeover"),
    (r"\b(hacked|breached|compromised)\b", "account takeover compromise"),
    (r"\b(phishy|scam email|fake email|suspicious email)\b", "phishing report"),
    (r"\b(leak|leaking|exfil|stole data|data theft)\b", "data exfiltration egress"),
    (r"\b(help|please|someone|us|my|got)\b", ""),
]


def rewrite_query(query: str) -> str:
    """Rewrite the user's words into the corpus's vocabulary."""
    out = query.lower()
    for pattern, replacement in REWRITES:
        out = re.sub(pattern, replacement, out)
    return " ".join(out.split())


def multi_query(query: str) -> list:
    """Several phrasings of one question. Retrieve with each, union the results.
    A real system asks a model for the variants; this is deterministic."""
    base = rewrite_query(query)
    variants = [query, base, f"runbook steps for {base}", f"how to respond to {base}"]
    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out

# ---------------------------------------------------------------- hybrid


def make_semantic_embed(embed_fn):
    """Wrap a bag-of-words embedder so it ignores identifier-shaped tokens
    (CVE-2026-2000, ERR-4471, ...). That is what a real embedding model does in
    effect: identifiers land nowhere useful in meaning-space. Without this the
    toy embedder would match the literal token and hide dense retrieval's blind
    spot."""
    ident = re.compile(r"\b(?:[a-z]+-)?\d{2,}(?:-\d+)*\b")

    def semantic_embed(text: str):
        return embed_fn(ident.sub(" ", text.lower()))
    return semantic_embed


def _minmax(scores: dict) -> dict:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi - lo < 1e-9:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


class HybridRetriever:
    """Document-level hybrid search: dense (embed+cosine) and sparse (BM25),
    fused either by weighted score (alpha) or by reciprocal rank fusion."""

    def __init__(self, corpus: dict, embed_fn, sim_fn):
        self.ids = list(corpus)
        self.texts = [corpus[i] for i in self.ids]
        self.embed, self.sim = embed_fn, sim_fn
        self.vecs = {i: embed_fn(t) for i, t in zip(self.ids, self.texts)}
        self.bm25 = BM25Okapi([tokens(t) for t in self.texts])

    def dense(self, query: str) -> dict:
        qv = self.embed(query)
        return {i: self.sim(qv, self.vecs[i]) for i in self.ids}

    def sparse(self, query: str) -> dict:
        scores = self.bm25.get_scores(tokens(query))
        return {i: float(s) for i, s in zip(self.ids, scores)}

    def search(self, query: str, alpha: float = 0.5, k: int = 5) -> list:
        """alpha=1 pure dense, alpha=0 pure sparse. Scores min-max normalised first."""
        d, s = _minmax(self.dense(query)), _minmax(self.sparse(query))
        fused = {i: round(alpha * d[i] + (1 - alpha) * s[i], 3) for i in self.ids}
        ranked = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{"doc": i, "fused": f, "dense": round(d[i], 3), "sparse": round(s[i], 3)}
                for i, f in ranked[:k]]

    def rrf(self, query: str, k: int = 5, c: int = 60) -> list:
        """Reciprocal rank fusion: no weights to tune, only ranks matter."""
        dense, sparse = self.dense(query), self.sparse(query)
        ranks = {}
        # Ties on one side are broken by the other side's score, so two passages the
        # embedder cannot tell apart are ordered by the exact tokens BM25 can see.
        for scores, tiebreak in ((dense, sparse), (sparse, dense)):
            order = sorted(scores, key=lambda i: (-scores[i], -tiebreak[i]))
            for r, i in enumerate(order, 1):
                ranks[i] = ranks.get(i, 0.0) + 1.0 / (c + r)
        ranked = sorted(ranks.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{"doc": i, "rrf": round(v, 4)} for i, v in ranked[:k]]
