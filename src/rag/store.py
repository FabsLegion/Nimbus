import chromadb
from sentence_transformers import SentenceTransformer

emb = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")  # understands English, Kannada, Hindi...
client = chromadb.PersistentClient("chroma")

def col():
    return client.get_collection("knowledge_base")
