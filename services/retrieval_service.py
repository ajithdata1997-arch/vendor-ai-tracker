from services.embedding_service import EmbeddingService
from services.db_service import update_embedding, search_by_vector
from services import llm_service


class RetrievalService:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    def index_vendor(self, vendor_id: int, name: str, phone: str, company_name: str, rate: str):
        text = f"Name: {name}, Phone: {phone}, Company: {company_name}, Rate: {rate}"
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
            f"Name: {r['name']}, Phone: {r['phone']}, "
            f"Company: {r['company_name']}, Rate: {r['rate']}"
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
