import os
from google import genai

from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.retrieval.service import RetrievalService
from src.llm.prompt import PromptBuilder

class AcademicChatbot:
    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.model_name = model_name
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.retriever = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

    def ask(self, query: str) -> str:

        contexts = self.retriever.retrieve(
            query=query,
            top_k=5,
        )

        prompt = PromptBuilder.build(
            query=query,
            contexts=contexts,
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        return response.text