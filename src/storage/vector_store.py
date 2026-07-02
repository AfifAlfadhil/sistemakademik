import chromadb
from chromadb.config import Settings

class VectorStore:
    def __init__(self, persist_directory: str = "./chroma_db", collection_name: str = "academic_docs"):
        """Inisialisasi ChromaDB."""
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # Inisialisasi client dalam mode persistent
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Get atau create collection dengan Cosine Similarity (default adalah L2)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
    def add_documents(self, chunks: list[dict], embeddings: list[list[float]]):
        """
        Menambahkan (upsert) chunks dan embeddings ke ChromaDB.
        
        Args:
            chunks: List of chunk dicts (harus ada chunk_id, content, dan metadata lainnya)
            embeddings: List of embedding vectors yang berkorespondensi
        """
        if not chunks or not embeddings:
            return
            
        if len(chunks) != len(embeddings):
            raise ValueError(f"Jumlah chunks ({len(chunks)}) tidak sama dengan jumlah embeddings ({len(embeddings)})")
            
        # Siapkan data untuk ChromaDB
        ids = []
        documents = []
        metadatas = []
        
        for chunk in chunks:
            ids.append(chunk["chunk_id"])
            documents.append(chunk["content"])
            
            # Ekstrak metadata (semua key selain id dan content)
            metadata = {
                "source_file": chunk.get("source_file", ""),
                "document_id": chunk.get("document_id", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "char_count": chunk.get("char_count", 0),
            }
            metadatas.append(metadata)
            
        # Upsert ke ChromaDB (add/update)
        # ChromaDB memproses embeddings, document text, ids, dan metadatas secara bersamaan
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

    def clear(self):
        """Menghapus isi collection"""
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)
        
    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """
        Mencari chunks paling relevan berdasarkan query_embedding (Vector Similarity Search).
        
        Args:
            query_embedding: Vector hasil embed_query()
            top_k: Jumlah hasil teratas yang dikembalikan
            
        Returns:
            List of dictionary berisi informasi chunk yang relevan dan skor kemiripannya
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format hasil
        formatted_results = []
        if not results["ids"] or not results["ids"][0]:
            return formatted_results
            
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            formatted_results.append({
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "distance": distance,
                "score": 1.0 - distance,  # Konversi Cosine Distance ke Cosine Similarity
                **results["metadatas"][0][i]  # Merge metadatas langsung ke dict
            })
            
        return formatted_results
        
    def delete_by_document(self, document_id: str):
        """Menghapus semua chunks milik sebuah dokumen."""
        self.collection.delete(
            where={"document_id": document_id}
        )
        
    def get_stats(self) -> dict:
        """Mengambil statistik collection (jumlah chunks)."""
        count = self.collection.count()

        return {
            "collection": self.collection_name,
            "persist_directory": self.persist_directory,
            "total_chunks": count,
            }

