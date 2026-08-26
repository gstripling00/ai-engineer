"""
Chapter 6 smoke test. Exits non-zero if any expectation fails, so CI can run it.

    python labs/chapter-06-rag-grounding-aegis/demo.py
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data.corpus import GOLDEN_SET, METADATA, all_docs                          # noqa: E402
from rag.pipeline import (STRATEGIES, VectorIndex, chunk_by_step, chunk_fixed,  # noqa: E402
                          cosine, embed, evaluate_strategies)
from rag.hybrid import HybridRetriever, make_semantic_embed, rewrite_query       # noqa: E402
from rag.advanced import (ParentChildIndex, grounded_answer, hit_rate,          # noqa: E402
                          index_retriever, mean_margin, mrr, rerank)
from rag import vectorstore                                                     # noqa: E402


def main() -> int:
    docs = all_docs()

    res = evaluate_strategies(docs, "detonate URLs in a sandbox and do not visit them directly", "rb_phishing")
    assert all(r["correct"] for r in res.values()), res
    assert res["sentence-window"]["score"] > res["hierarchical"]["score"], res
    print("chunking    ok  all four strategies correct; sentence-window wins on margin")

    steps = chunk_by_step(docs["rb_account_takeover"])
    assert [c.count("Step") for c in steps if "Step" in c] == [1] * 5, steps
    fixed = chunk_fixed(docs["rb_account_takeover"])
    assert any(re.search(r"Step \d+:$", c) for c in fixed), fixed        # an orphaned step label
    assert any(c[0].islower() for c in fixed), fixed                      # a chunk starting mid-word
    print("structure   ok  fixed chunking orphans a step label and starts mid-word; step-aware keeps every step whole")

    idx = VectorIndex().index(docs, "semantic", METADATA)
    hits = idx.retrieve("how do I contain an account takeover and check for data egress", k=2)
    ans = grounded_answer("contain an account takeover", hits)
    bad = grounded_answer("contain an account takeover", hits, fabricate=True)
    assert ans.supported and not bad.supported and "rb_account_takeover" in ans.citations, (ans, bad)
    assert all(c.meta["type"] == "advisory" for _s, c in idx.retrieve("bypass", k=3, where={"type": "advisory"}))
    print("grounding   ok  extractive answer passes the check; fabricated sentence is flagged")

    assert rewrite_query("help my account got taken over") == "account takeover"
    print("rewrite     ok  user vocabulary mapped to corpus vocabulary")

    corpus = dict(docs)
    tmpl = "CVE-2026-{} advisory. Severity high. Affected component: VPN appliance. Mitigation: apply the vendor patch and rotate credentials."
    corpus["cve_2026_3000"], corpus["cve_2026_4000"] = tmpl.format(3000), tmpl.format(4000)
    ret = HybridRetriever(corpus, make_semantic_embed(embed), cosine)
    q = "CVE-2026-4000 mitigation"
    dense = sorted(ret.dense(q).items(), key=lambda kv: -kv[1])[:2]
    assert abs(dense[0][1] - dense[1][1]) < 1e-9, dense                      # dense ties
    assert ret.search(q, alpha=0.0)[0]["doc"] == "cve_2026_4000"
    assert ret.search(q, alpha=0.5)[0]["doc"] == "cve_2026_4000"
    assert ret.rrf(q)[0]["doc"] == "cve_2026_4000"
    assert mean_margin(idx, GOLDEN_SET) > 0
    print("hybrid      ok  BM25 and fusion pin the exact identifier dense search blurs")

    cands = idx.retrieve("force a password reset and require re-enrollment of MFA", k=6)
    top = rerank("force a password reset and require re-enrollment of MFA", cands, top_n=1)[0][1]
    assert "re-enrollment of MFA" in top.text, top.text
    print("rerank      ok  cross-encoder stand-in promotes the exact passage")

    pc = ParentChildIndex(docs)
    score, child, parent = pc.retrieve("revoke active sessions", k=1)[0]
    assert "revoke active sessions" in child.text and len(parent) > len(child.text)
    print("parent-doc  ok  matched one sentence, returned its whole section")

    r = index_retriever(idx)
    assert hit_rate(r, GOLDEN_SET, k=1) >= 0.75 and mrr(r, GOLDEN_SET) >= 0.8, (hit_rate(r, GOLDEN_SET), mrr(r, GOLDEN_SET))
    print(f"metrics     ok  hit@1={hit_rate(r, GOLDEN_SET, 1)}  mrr={mrr(r, GOLDEN_SET)} on the golden set")

    with tempfile.TemporaryDirectory() as d:
        col = vectorstore.build_collection(d, docs, METADATA)
        col2 = vectorstore.open_collection(d)
        assert col2.count() == col.count() > 0
        out = vectorstore.query(col2, "detonate URLs in a sandbox", k=1)
        assert out[0][0] == "rb_phishing", out
        out = vectorstore.query(col2, "mitigation", k=2, where={"type": "advisory"})
        assert all(o[0].startswith("cve") for o in out), out
    print("chroma      ok  persisted, reopened, metadata-filtered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
