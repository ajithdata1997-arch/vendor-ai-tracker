from sentence_transformers import SentenceTransformer


class EmbeddingService:
    _model: SentenceTransformer | None = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if EmbeddingService._model is None:
            EmbeddingService._model = SentenceTransformer(model_name)
        self.model = EmbeddingService._model

    def embed_text(self, text: str) -> list[float]:
        return self.model.encode(text, convert_to_numpy=True).tolist()
