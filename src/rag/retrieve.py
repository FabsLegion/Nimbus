from src.rag.store import emb, col

def retrieve(query, scholarship):
    """Return (current_chunks, older_chunks, best_distance). Newest year/version wins."""
    r = col().query(query_embeddings=emb.encode([query]).tolist(), n_results=10,
                    where={"scholarship": scholarship},
                    include=["documents", "metadatas", "distances"])
    if not r["documents"] or not r["documents"][0]:
        return [], [], float("inf")
    
    distances = r.get("distances", [[]])[0]
    best_dist = distances[0] if distances else float("inf")

    hits = [{"text": d, "dist": dist, **m} for d, m, dist in zip(r["documents"][0], r["metadatas"][0], distances)]
    hits.sort(key=lambda h: (h["year"], h["version"]), reverse=True)
    best = (hits[0]["year"], hits[0]["version"])
    current = [h for h in hits if (h["year"], h["version"]) == best]
    older = [h for h in hits if (h["year"], h["version"]) != best]
    return current, older, best_dist
