"""
service.py — Layanan Embedding menggunakan Google Gemini

Mengubah teks chunk menjadi representasi vektor numerik (768 dimensi).
Menggunakan model `text-embedding-004`.
"""

import os
import time
from google import genai

class EmbeddingService:
    def __init__(self, model_name: str = "text-embedding-004"):
        self.model_name = model_name
        self._init_client()
        
    def _init_client(self):
        """Inisialisasi Gemini client."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY belum diset atau masih menggunakan nilai default di .env")
        
        self.client = genai.Client(api_key=api_key)
        
    def embed_texts(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT", batch_size: int = 100) -> list[list[float]]:
        """
        Embed banyak teks sekaligus (batch processing).
        
        Args:
            texts: List teks yang akan di-embed
            task_type: Jenis embedding ("RETRIEVAL_DOCUMENT" untuk indexing, "RETRIEVAL_QUERY" untuk pertanyaan)
            batch_size: Jumlah maksimal teks per API call (max 100 untuk Gemini)
            
        Returns:
            List of embedding vectors (list of list of floats)
        """
        if not texts:
            return []
            
        all_embeddings = []
        
        # Proses per batch
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            # Rate limiting / Backoff sederhana
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Construct list of Content objects to embed separate documents in a batch
                    contents = [
                        genai.types.Content(parts=[genai.types.Part.from_text(text=t)])
                        for t in batch_texts
                    ]
                    response = self.client.models.embed_content(
                        model=self.model_name,
                        contents=contents,
                        config=genai.types.EmbedContentConfig(
                            task_type=task_type,
                        )
                    )
                    
                    # Ekstrak nilai embedding
                    batch_embeddings = [emb.values for emb in response.embeddings]
                    all_embeddings.extend(batch_embeddings)
                    break
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"❌ Gagal embed batch {i}-{i+batch_size}: {e}")
                        raise
                    print(f"⚠️  Rate limit/Error dari Gemini, retrying in {2**(attempt+1)}s...")
                    time.sleep(2**(attempt+1))
                    
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """
        Embed pertanyaan user untuk pencarian (retrieval).
        """
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=query,
            config=genai.types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
            )
        )
        return response.embeddings[0].values
