"""
Advanced RAG: reranking, parent-document retrieval, grounded generation with
citations, a grounding check, and retrieval metrics.

Every piece is a deterministic stand-in for the model-backed version with the
same interface, so the notebook runs offline and CI can assert on it.
"""
import re
from dataclasses import dataclass

from .pipeline import Chunk, VectorIndex, _sentences, cosine, embed, tokens

# ---------------------------------------------------------------- reranking


def _bigrams(text: str) -> set:
    toks = tokens(text)
    return set(zip(toks, toks[1:]))


def rerank_score(query: str, text: str) -> float:
    """A stand-in for a cross-encoder. First-stage retrieval is cheap and
    approximate; the reranker reads query and passage TOGETHER and scores the
    pair. Here: phrase (bigram) overlap plus exact-token coverage, which rewards
    passages that say what the query says, in the order it says it."""
    q_bi, t_bi = _bigrams(query), _bigrams(text)
    q_tok, t_tok = set(tokens(query)), set(tokens(text))
    phrase = len(q_bi & t_bi) / len(q_bi) if q_bi else 0.0
    coverage = len(q_tok & t_tok) / len(q_tok) if q_tok else 0.0
    return round(0.7 * phrase + 0.3 * coverage, 3)


def rerank(query: str, candidates: list, top_n: int = 3) -> list:
    """candidates: [(first_stage_score, Chunk)]. Returns [(rerank_score, Chunk)]."""
    scored = [(rerank_score(query, c.text), c) for _s, c in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_n]

# ---------------------------------------------------------------- parent-document retrieval


class ParentChildIndex:
    """Match on small children (one sentence), return the whole parent section.
    Sharp matching, full-context generation — the two things a single chunk
    size cannot give you at once."""

    def __init__(self, docs: dict, parent_sents: int = 3):
        self.children: list[Chunk] = []
        self.parents: dict = {}
        for doc_id, text in docs.items():
            sents = _sentences(text)
            for p, i in enumerate(range(0, len(sents), parent_sents)):
                parent_id = f"{doc_id}#p{p}"
                self.parents[parent_id] = " ".join(sents[i:i + parent_sents])
                for s in sents[i:i + parent_sents]:
                    self.children.append(Chunk(doc_id, s, embed(s), {"parent": parent_id}))

    def retrieve(self, query: str, k: int = 2) -> list:
        """Returns [(score, matched_child, parent_text)] deduplicated by parent."""
        qv = embed(query)
        scored = sorted(((cosine(qv, c.vec), c) for c in self.children),
                        key=lambda x: x[0], reverse=True)
        out, seen = [], set()
        for score, child in scored:
            pid = child.meta["parent"]
            if pid in seen:
                continue
            seen.add(pid)
            out.append((score, child, self.parents[pid]))
            if len(out) == k:
                break
        return out

# ---------------------------------------------------------------- grounded generation


@dataclass
class GroundedAnswer:
    text: str
    citations: list          # doc ids the answer drew from
    supported: bool          # did every sentence pass the grounding check
    unsupported: list        # sentences that did not


def _supported_by(sentence: str, context: str, threshold: float = 0.5) -> bool:
    """A sentence is supported if most of its content words appear in the context."""
    s_tok, c_tok = set(tokens(sentence)), set(tokens(context))
    return bool(s_tok) and len(s_tok & c_tok) / len(s_tok) >= threshold


def grounding_check(answer: str, context: str) -> tuple:
    """Return (all_supported, [unsupported sentences]). This is the check that
    makes it RAG rather than search: the answer must be built FROM the context."""
    bad = [s for s in _sentences(answer) if not _supported_by(s, context)]
    return (not bad, bad)


def grounded_answer(query: str, hits: list, fabricate: bool = False) -> GroundedAnswer:
    """Deterministic 'model': answer extractively from the retrieved passages,
    citing each. With fabricate=True it appends a sentence that is NOT in the
    context — the thing a real model does when it answers from training instead
    of from what was retrieved."""
    context = " ".join(c.text for _s, c in hits)
    q_tok = set(tokens(query))
    picked = []
    for _s, c in hits:
        for sent in _sentences(c.text):
            if q_tok & set(tokens(sent)) and sent not in picked:
                picked.append(sent)
    text = " ".join(picked[:3]) or "The retrieved passages do not answer this."
    if fabricate:
        text += " Also deploy the zero-trust mesh and rotate the HSMs."
    ok, bad = grounding_check(text, context)
    return GroundedAnswer(text=text,
                          citations=sorted({c.doc_id for _s, c in hits}),
                          supported=ok, unsupported=bad)

# ---------------------------------------------------------------- retrieval metrics


def hit_rate(retriever, golden: list, k: int = 1) -> float:
    """Fraction of queries whose expected doc appears in the top-k."""
    hits = 0
    for query, expected in golden:
        docs = retriever(query, k)
        hits += expected in docs
    return round(hits / len(golden), 3)


def mrr(retriever, golden: list, k: int = 5) -> float:
    """Mean reciprocal rank: 1 if the right doc is first, 1/2 if second, ..."""
    total = 0.0
    for query, expected in golden:
        docs = retriever(query, k)
        if expected in docs:
            total += 1.0 / (docs.index(expected) + 1)
    return round(total / len(golden), 3)


def index_retriever(index: VectorIndex):
    """Adapter: VectorIndex -> (query, k) -> [doc ids], deduplicated by document."""
    def _run(query: str, k: int) -> list:
        out = []
        for _s, c in index.retrieve(query, k=len(index.chunks)):
            if c.doc_id not in out:
                out.append(c.doc_id)
            if len(out) == k:
                break
        return out
    return _run


def mean_margin(index: VectorIndex, golden: list) -> float:
    """Average gap between the best chunk of the expected document and the best
    chunk of any OTHER document. Pass/fail throws this number away; it is the
    one that predicts behaviour at scale."""
    gaps = []
    for query, expected in golden:
        best_right, best_wrong = 0.0, 0.0
        for score, chunk in index.retrieve(query, k=len(index.chunks)):
            if chunk.doc_id == expected:
                best_right = max(best_right, score)
            else:
                best_wrong = max(best_wrong, score)
        gaps.append(best_right - best_wrong)
    return round(sum(gaps) / len(gaps), 3)
