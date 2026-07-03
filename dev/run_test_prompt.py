import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.retrieval.service import RetrievalService
from src.llm.prompt import PromptBuilder
from src.config import config

# Inisialisasi service dari config
embedder = EmbeddingService(
    model_name=config["embedding"]["model"],
)

vector_store = VectorStore(
    persist_directory=config["vector_store"]["persist_directory"],
    collection_name=config["vector_store"]["collection_name"],
)

retriever = RetrievalService(
    embedding_service=embedder,
    vector_store=vector_store,
)

query = input("Pertanyaan: ").strip()

contexts = retriever.retrieve(query)

prompt = PromptBuilder().build(
    query=query,
    contexts=contexts,
)

print("\n" + "=" * 80)
print("PROMPT")
print("=" * 80)
print(prompt)