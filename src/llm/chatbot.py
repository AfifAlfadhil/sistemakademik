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

    def ask(self, query: str) -> tuple[str, list[dict]]:

        top_k = config.get("retrieval", {}).get("top_k", 15)
        contexts = self.retriever.retrieve(
            query=query,
            top_k=top_k,
        )

        if not contexts:
            return "Maaf, informasi tersebut tidak ditemukan pada dokumen yang tersedia.", []

        prompt = PromptBuilder.build(
            query=query,
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