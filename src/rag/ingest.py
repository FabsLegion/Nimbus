import glob
import fitz  # PyMuPDF
from src.rag.store import emb, client

def run():
    try:
        client.delete_collection("knowledge_base")
    except Exception:
        pass
    col = client.create_collection("knowledge_base")
    for path in glob.glob("data/scholarships/*.pdf"):
        text = "\n".join(p.get_text() for p in fitz.open(path))
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        name, year, ver = [x.strip() for x in lines[0].split("|")]
        meta = {"scholarship": name, "year": int(year), "version": int(ver.lstrip("v")),
                "source": path.replace("\\", "/").split("/")[-1]}
        body = lines[1:]   # each line is one chunk (the files are tiny)
        col.add(ids=[f"{meta['source']}-{i}" for i in range(len(body))],
                documents=body, embeddings=emb.encode(body).tolist(),
                metadatas=[meta] * len(body))
    print("Indexed", col.count(), "chunks")

if __name__ == "__main__":
    run()
