import os
from google import genai

from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.retrieval.service import RetrievalService
from src.llm.prompt import PromptBuilder
from src.config import config

class AcademicChatbot:
    def __init__(
        self,
        model_name: str = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.model_name = model_name or config.get("llm", {}).get("model", "gemini-2.5-flash")
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.retriever = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

    def condense_query(self, query: str, history: list[dict]) -> str:
        history_str = ""
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role_label}: {msg['content']}\n"
        
        prompt = f"""
Berikut adalah riwayat percakapan antara User dan Assistant, diikuti oleh pertanyaan terbaru dari User yang membutuhkan konteks dari percakapan sebelumnya agar dapat dipahami secara mandiri.

TUGAS:
Tulis ulang pertanyaan terbaru tersebut menjadi satu pertanyaan mandiri (standalone question) dalam bahasa Indonesia yang lengkap, spesifik, dan dapat dipahami tanpa perlu melihat riwayat percakapan lagi.

ATURAN:
1. JANGAN menjawab pertanyaan tersebut. Hanya tulis ulang pertanyaannya.
2. Pertahankan kata kunci penting (seperti nama program, nama bank, UKT, dll).
3. Jika pertanyaan terbaru sudah mandiri dan tidak memerlukan konteks dari riwayat percakapan, tulis ulang persis seperti pertanyaan asli.

Riwayat Percakapan:
{history_str}
Pertanyaan Terbaru: {query}

Pertanyaan Mandiri:
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            condensed = response.text.strip()
            if condensed.startswith('"') and condensed.endswith('"'):
                condensed = condensed[1:-1]
            return condensed
        except Exception as e:
            print(f"Error condensing query: {e}")
            return query
    def ask(self, query: str, history: list[dict] | None = None) -> tuple[str, list[dict]]:
        search_query = query
        if history:
            words = query.strip().split()
            if len(words) <= 4 or len(query) <= 25:
                search_query = self.condense_query(query, history)
                print(f"Query condensation (Optimized): '{query}' -> '{search_query}'")

        top_k = config.get("retrieval", {}).get("top_k", 15)
        contexts = self.retriever.retrieve(
            query=search_query,
            top_k=top_k,
        )

        if not contexts:
            return "Maaf, informasi tersebut tidak ditemukan pada dokumen yang tersedia.", []

        prompt = PromptBuilder.build(
            query=search_query,
            contexts=contexts,
        )

        llm_config = config.get("llm", {})
        temperature = llm_config.get("temperature", 0.2)
        max_tokens = llm_config.get("max_tokens", 2048)
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            return response.text, contexts
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                return "Maaf, sistem sedang menerima terlalu banyak permintaan (Rate Limit API tercapai). Mohon tunggu sekitar 20-30 detik sebelum bertanya kembali.", []
            return f"Terjadi kesalahan saat menghubungi layanan AI: {error_str}", []