from src.rag.store import emb, col

def retrieve(query, scholarship):
    """Return (current_chunks, older_chunks). Newest year/version wins."""
    r = col().query(query_embeddings=emb.encode([query]).tolist(), n_results=10,
                    where={"scholarship": scholarship})
    hits = [{"text": d, **m} for d, m in zip(r["documents"][0], r["metadatas"][0])]
    if not hits:
        return [], []
    hits.sort(key=lambda h: (h["year"], h["version"]), reverse=True)
    best = (hits[0]["year"], hits[0]["version"])
    current = [h for h in hits if (h["year"], h["version"]) == best]
    older = [h for h in hits if (h["year"], h["version"]) != best]
    return current, older
