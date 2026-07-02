from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ):
        """Inisialisasi Retrieval Service."""
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[dict]:
        """
        Melakukan retrieval berdasarkan query pengguna.

        Args:
            query: Pertanyaan pengguna.
            top_k: Jumlah maksimum chunk yang diambil.
            min_score: Nilai minimum similarity score.

        Returns:
            List chunk yang relevan.
        """
        if not query.strip():
            raise ValueError("Query tidak boleh kosong.")

        # Embed query
        query_embedding = self.embedding_service.embed_query(query)

        # Similarity search
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
        )

        # Filter berdasarkan similarity score
        return [
            result
            for result in results
            if result["score"] >= min_score
        ]