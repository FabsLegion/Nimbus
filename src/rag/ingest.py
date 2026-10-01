"""Knowledge base ingestion and per-document ChromaDB chunk management."""
import glob
import fitz  # PyMuPDF
from src.rag.store import emb, client

def get_or_create_col():
    """Retrieve or create the knowledge base Chroma collection."""
    try:
        return client.get_collection("knowledge_base")
    except Exception:
        return client.create_collection("knowledge_base")

def delete_source_chunks(source_filename: str):
    """Delete ONLY chunks corresponding to a specific source file."""
    col = get_or_create_col()
    try:
        col.delete(where={"source": source_filename})
    except Exception:
        pass

def add_document_chunks(source_filename: str, scholarship: str, year: int, version: int, chunks: list[dict]):
    """Add chunks for a single document to Chroma without deleting other documents."""
    col = get_or_create_col()
    delete_source_chunks(source_filename)
    
    docs = [c["text"] for c in chunks if c.get("text", "").strip()]
    if not docs:
        return 0
    
    metas = [
        {
            "scholarship": scholarship,
            "year": int(year),
            "version": int(version),
            "source": source_filename,
            "page": int(c.get("page", 1)),
        }
        for c in chunks if c.get("text", "").strip()
    ]
    ids = [f"{source_filename}-{i}" for i in range(len(docs))]
    
    col.add(ids=ids, documents=docs, embeddings=emb.encode(docs).tolist(), metadatas=metas)
    return len(docs)

def run():
    """Ingest existing scholarship PDFs in data/scholarships/ without dropping other data."""
    col = get_or_create_col()
    for path in glob.glob("data/scholarships/*.pdf"):
        source = path.replace("\\", "/").split("/")[-1]
        text = "\n".join(p.get_text() for p in fitz.open(path))
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        try:
            name, year, ver = [x.strip() for x in lines[0].split("|")]
            body = lines[1:]
            chunks = [{"text": l, "page": 1} for l in body]
            add_document_chunks(source, name, int(year), int(ver.lstrip("v")), chunks)
        except Exception as e:
            print(f"Skipping {path}: {e}")
    print("Indexed", col.count(), "chunks")

if __name__ == "__main__":
    run()
