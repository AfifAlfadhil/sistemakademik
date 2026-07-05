from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.config import config

class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ):
        """Inisialisasi Retrieval Service."""
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def heuristic_rerank(self, results: list[dict], query: str) -> list[dict]:
        q = query.lower()
        time_keywords = ["tanggal", "kapan", "jadwal", "batas", "bulan", "tahun", "hari", "deadline", "date", "schedule", "when"]
        is_time_query = any(k in q for k in time_keywords)
        
        months = ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november", "desember"]
        
        reranked = []
        for r in results:
            item = dict(r)
            content_lower = item["content"].lower()
            score = item["score"]
            
            if is_time_query:
                # Boost if it contains a month
                has_month = any(m in content_lower for m in months)
                if has_month:
                    score += 0.15
                # Boost if it contains calendar/registrations keywords
                for k in ["jadwal", "tanggal", "kalender", "herregistrasi", "registrasi"]:
                    if k in content_lower:
                        score += 0.05
                        
            # Boost if it matches query terms directly
            query_words = [w for w in q.split() if len(w) > 2]
            for qw in query_words:
                if qw in content_lower:
                    score += 0.02
                    
            item["score"] = score
            reranked.append(item)
            
        reranked.sort(key=lambda x: x["score"], reverse=True)
        return reranked

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        min_score: float = None,
    ) -> list[dict]:
        top_k = top_k or config.get("retrieval", {}).get("top_k", 5)
        min_score = min_score or config.get("retrieval", {}).get("min_score", 0.4)
        """
        Melakukan retrieval berdasarkan query pengguna dengan optimasi heuristik.

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

        # Ambil chunks lebih banyak untuk diproses reranking (misal 2 kali top_k, minimal 25)
        search_top_k = max(top_k * 2, 25)
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=search_top_k,
        )

        # Lakukan reranking heuristik
        reranked_results = self.heuristic_rerank(results, query)

        # Filter berdasarkan similarity score setelah dirangking kembali, batasi ke top_k
        filtered = [
            result
            for result in reranked_results
            if result["score"] >= min_score
        ]
        
        return filtered[:top_k]