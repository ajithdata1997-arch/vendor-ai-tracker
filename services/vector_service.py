import os
from pathlib import Path
import chromadb
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = str(PROJECT_ROOT / os.getenv("CHROMA_PATH", "data/chroma_store"))


class VectorService:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.client.get_or_create_collection(
            name="vendors",
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, doc_id: str, text: str, embedding: list[float], metadata: dict = None):
        self.collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def query(self, embedding: list[float], top_k: int = 5) -> list[dict]:
        count = self.collection.count()
        if count == 0:
            return []
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
        )
        docs = []
        for i, doc_id in enumerate(results["ids"][0]):
            docs.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return docs
