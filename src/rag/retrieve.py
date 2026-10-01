"""Hybrid retrieval combining ChromaDB dense semantic search with BM25 keyword search via RRF."""
from rank_bm25 import BM25Okapi
from src.rag.store import emb, col

def retrieve(query, scholarship):
    """Return (current_chunks, older_chunks, best_distance).
    Newest year/version wins. Uses Reciprocal Rank Fusion over Dense + BM25.
    """
    c = col()
    dense_res = c.query(
        query_embeddings=emb.encode([query]).tolist(),
        n_results=15,
        where={"scholarship": scholarship},
        include=["documents", "metadatas", "distances"]
    )
    
    if not dense_res["documents"] or not dense_res["documents"][0]:
        return [], [], float("inf")
    
    distances = dense_res["distances"][0]
    best_dist = distances[0] if distances else float("inf")
    
    # 1. Dense search ranking
    dense_docs = dense_res["documents"][0]
    dense_metas = dense_res["metadatas"][0]
    dense_ranks = {doc: idx for idx, doc in enumerate(dense_docs)}
    
    # 2. BM25 keyword search over all chunks for this scholarship
    all_chunks = c.get(where={"scholarship": scholarship}, include=["documents", "metadatas"])
    bm25_ranks = {}
    if all_chunks["documents"]:
        corpus = [doc.lower().split() for doc in all_chunks["documents"]]
        bm25 = BM25Okapi(corpus)
        query_tokens = query.lower().split()
        if query_tokens:
            scores = bm25.get_scores(query_tokens)
            sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            bm25_ranks = {all_chunks["documents"][idx]: rank for rank, idx in enumerate(sorted_idx)}

    # 3. Reciprocal Rank Fusion (RRF)
    all_doc_keys = set(dense_docs).union(set(bm25_ranks.keys()))
    meta_lookup = {}
    dist_lookup = {}
    for d, m, dist in zip(dense_docs, dense_metas, distances):
        meta_lookup[d] = m
        dist_lookup[d] = dist
    for d, m in zip(all_chunks.get("documents", []), all_chunks.get("metadatas", [])):
        if d not in meta_lookup:
            meta_lookup[d] = m
            dist_lookup[d] = best_dist + 5.0

    scored_hits = []
    for d in all_doc_keys:
        d_rank = dense_ranks.get(d, 100)
        b_rank = bm25_ranks.get(d, 100)
        rrf_score = (1.0 / (60 + d_rank)) + (1.0 / (60 + b_rank))
        m = meta_lookup.get(d, {"scholarship": scholarship, "year": 2026, "version": 1, "source": ""})
        scored_hits.append({
            "text": d,
            "dist": dist_lookup.get(d, best_dist),
            "rrf": rrf_score,
            **m
        })

    # Sort candidates by (year, version) descending, then RRF score
    scored_hits.sort(key=lambda h: (h.get("year", 0), h.get("version", 0), h["rrf"]), reverse=True)

    if not scored_hits:
        return [], [], float("inf")

    best_version = (scored_hits[0]["year"], scored_hits[0]["version"])
    current = [h for h in scored_hits if (h["year"], h["version"]) == best_version]
    older = [h for h in scored_hits if (h["year"], h["version"]) != best_version]
    
    return current, older, best_dist
