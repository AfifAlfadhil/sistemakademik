"""
seed_database.py — Skrip untuk melakukan Ingestion & Embedding awal (Production)

Script ini membaca seluruh file PDF dari folder `data/uploads/`,
lalu mengekstrak, memotong (chunking), dan menyimpannya ke dalam
Vector Database (ChromaDB) menggunakan Google Gemini.
"""

import sys
import os
import uuid
import time
from pathlib import Path

# Tambahkan root directory project ke sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import yaml
from src.ingestion.pdf_extractor import extract_pdf_full_ocr
from src.ingestion.chunking import chunk_text
from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore

def load_config() -> dict:
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        print("⚠️  config.yaml tidak ditemukan, menggunakan default")
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    upload_dir = PROJECT_ROOT / "data" / "uploads"
    
    if not upload_dir.exists():
        print(f"❌ Folder uploads tidak ditemukan: {upload_dir}")
        sys.exit(1)
        
    pdf_files = list(upload_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"⚠️ Tidak ada file PDF di {upload_dir}.")
        sys.exit(0)
        
    print("=" * 60)
    print(f"🚀 MULAI SEEDING DATABASE ({len(pdf_files)} Dokumen)")
    print("=" * 60)
    
    # Inisialisasi Services
    embed_model_name = config.get("embedding", {}).get("model", "text-embedding-004")
    embed_batch_size = config.get("embedding", {}).get("batch_size", 100)
    task_type_doc = config.get("embedding", {}).get("task_type_document", "RETRIEVAL_DOCUMENT")
    
    persist_dir = config.get("vector_store", {}).get("persist_directory", "./chroma_db")
    collection_name = config.get("vector_store", {}).get("collection_name", "academic_docs")
    
    embedding_service = EmbeddingService(model_name=embed_model_name)
    vector_store = VectorStore(persist_directory=persist_dir, collection_name=collection_name)
    
    # Bersihkan Vector Database lama agar tidak duplikat
    print("🧹 Membersihkan Vector Database lama...")
    vector_store.clear()
    
    total_start = time.time()
    total_chunks_added = 0
    
    for pdf_path in pdf_files:
        filename = pdf_path.name
        
        print(f"\n📄 Memproses: {filename}")
        
        # 1. OCR Extraction
        print(f"   🔍 Ekstraksi Teks (OCR)...")
        ocr_config = config.get("ocr", {})
        preprocessing_config = ocr_config.get("preprocessing", {})
        
        try:
            extraction_result = extract_pdf_full_ocr(
                pdf_path=str(pdf_path),
                dpi=ocr_config.get("dpi", 300),
                tesseract_lang=ocr_config.get("tesseract_lang", "ind"),
                psm_text=ocr_config.get("tesseract_psm_text", 6),
                psm_table=ocr_config.get("tesseract_psm_table", 4),
                psm_mixed=ocr_config.get("tesseract_psm_mixed", 3),
                preprocessing_config=preprocessing_config,
            )
            raw_text = extraction_result["text"]
            
            # 2. Chunking
            print(f"   ✂️  Memotong teks (Chunking)...")
            chunking_config = config.get("ingestion", {})
            chunks = chunk_text(
                text=raw_text,
                source_file=filename,
                document_id=str(uuid.uuid4()),
                chunk_size=chunking_config.get("chunk_size", 1000),
                chunk_overlap=chunking_config.get("chunk_overlap", 150),
            )
            
            valid_chunks = [c for c in chunks if c.get("content", "").strip()]
            if not valid_chunks:
                print("   ⚠️ Tidak ada chunk valid.")
                continue
                
            print(f"   🧠 Meng-embed {len(valid_chunks)} chunks...")
            texts = [c["content"] for c in valid_chunks]
            embeddings = embedding_service.embed_texts(texts, batch_size=embed_batch_size, task_type=task_type_doc)
            
            print("   💾 Menyimpan ke Chroma DB...")
            vector_store.add_documents(valid_chunks, embeddings)
            total_chunks_added += len(valid_chunks)
            print("   ✅ Sukses!")
            
        except Exception as e:
            print(f"   ❌ Gagal memproses {filename}: {e}")

    total_time = time.time() - total_start
    print("\n" + "=" * 60)
    print("🏁 SEEDING SELESAI")
    print(f"   Total Chunks Ditambahkan : {total_chunks_added}")
    print(f"   Waktu Eksekusi           : {total_time:.1f} detik")
    print("=" * 60)

if __name__ == "__main__":
    main()
