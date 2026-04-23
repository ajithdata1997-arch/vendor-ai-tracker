from services.embedding_service import EmbeddingService
from services.db_service import update_embedding, search_by_vector
from services import llm_service


class RetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    def index_vendor(self, vendor_id: int, fields: dict):
        text = ", ".join(f"{k}: {v}" for k, v in fields.items() if v)
        embedding = self.embedding_service.embed_text(text)
        update_embedding(vendor_id, embedding)

    def answer(self, query: str) -> str:
        embedding = self.embedding_service.embed_text(query)
        results = search_by_vector(embedding, top_k=5)

        if not results:
            return (
                "No vendor information found yet.\n\n"
                "Say **'add vendor'** to submit your first vendor!"
            )

        context = "\n".join(
            ", ".join(f"{k}: {v}" for k, v in r.items() if k not in ("id", "created_at", "distance") and v)
            for r in results
        )
        system = (
            "You are a helpful vendor management assistant. "
            "Answer questions about vendors concisely and clearly, "
            "based only on the provided context. "
            "If the answer isn't in the context, say so."
        )
        prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
        return llm_service.generate(prompt, system)
