"""
run_test_retrieval.py

Script untuk menguji Retrieval pada ChromaDB.
"""

from pathlib import Path
import sys
import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.retrieval.service import RetrievalService


def main():
    with open(PROJECT_ROOT / "config.yaml", "r") as f:
        config = yaml.safe_load(f)

    embedding_service = EmbeddingService(
        model_name=config["embedding"]["model"]
    )

    vector_store = VectorStore(
        persist_directory=config["vector_store"]["persist_directory"],
        collection_name=config["vector_store"]["collection_name"],
    )

    retriever = RetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    query = input("Masukkan pertanyaan: ").strip()

    results = retriever.retrieve(
        query=query,
        top_k=5,
    )

    if not results:
        print("❌ Tidak ada hasil yang relevan.")
        return

    print("\n===== HASIL RETRIEVAL =====\n")

    for i, r in enumerate(results, start=1):
        print(f"[{i}]")
        print(f"Score : {r['score']:.4f}")
        print(f"Distance : {r['distance']:.4f}")
        print(f"File : {r['source_file']}")
        print(f"Chunk : {r['chunk_index']}")
        print("-" * 40)
        print(r["content"])
        print("=" * 80)


if __name__ == "__main__":
    main()