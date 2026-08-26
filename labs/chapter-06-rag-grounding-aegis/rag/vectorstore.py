"""
A real vector database: Chroma, persisted to disk, with metadata filtering.

Two honesty notes. First, Chroma's default embedding function downloads a
model on first use; to keep the lab offline and deterministic we pass our own
vectors in explicitly (hashed term-frequency -> fixed-width float list). The
*database* is real; only the embedder is the book's stand-in. Second, the
point of this module is what a vector store adds over VectorIndex in
pipeline.py: persistence, metadata filters, and scale — not a different idea.
"""
import hashlib

from .pipeline import STRATEGIES, tokens

DIM = 256


def hashed_vector(text: str, dim: int = DIM) -> list:
    """Bag-of-words hashed into a fixed-width vector (the 'hashing trick')."""
    vec = [0.0] * dim
    for t in tokens(text):
        h = int(hashlib.md5(t.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


def build_collection(path: str, docs: dict, metadata: dict, strategy: str = "semantic",
                     name: str = "aegis_runbooks"):
    """(Re)build a persistent Chroma collection from the corpus."""
    import chromadb
    client = chromadb.PersistentClient(path=path)
    try:
        client.delete_collection(name)
    except Exception:
        pass
    col = client.create_collection(name, metadata={"hnsw:space": "cosine"})
    ids, texts, vecs, metas = [], [], [], []
    for doc_id, text in docs.items():
        for n, piece in enumerate(STRATEGIES[strategy](text)):
            ids.append(f"{doc_id}#{n}")
            texts.append(piece)
            vecs.append(hashed_vector(piece))
            metas.append({"doc": doc_id, **metadata.get(doc_id, {})})
    col.add(ids=ids, documents=texts, embeddings=vecs, metadatas=metas)
    return col


def open_collection(path: str, name: str = "aegis_runbooks"):
    import chromadb
    return chromadb.PersistentClient(path=path).get_collection(name)


def query(col, text: str, k: int = 3, where: dict | None = None) -> list:
    """Returns [(doc_id, similarity, passage)]. Chroma returns cosine DISTANCE."""
    res = col.query(query_embeddings=[hashed_vector(text)], n_results=k, where=where)
    out = []
    for meta, dist, passage in zip(res["metadatas"][0], res["distances"][0], res["documents"][0]):
        out.append((meta["doc"], round(1 - dist, 3), passage))
    return out
