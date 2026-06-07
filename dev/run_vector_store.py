"""
run_vector_store.py — Script untuk Embed dan Simpan ke Chroma DB

Script ini dibuat khusus untuk memproses file chunks JSON yang dihasilkan oleh ingestion,
menghasilkan vektor embedding, dan menyimpannya ke Chroma DB.
Di akhir proses, ia juga akan menyimpan file sampel human-readable ke direktori `data/eval/` 
untuk keperluan monitoring manual dan evaluasi.
"""

import sys
import os
import json
import glob
from pathlib import Path

# Tambahkan root directory project ke sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import yaml
from src.embedding.service import EmbeddingService
from src.storage.vector_store import VectorStore

def load_config() -> dict:
    """Load konfigurasi dari config.yaml."""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        print("⚠️  config.yaml tidak ditemukan, menggunakan default")
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    
    # Inisialisasi Services
    embed_model_name = config.get("embedding", {}).get("model", "text-embedding-004")
    embed_batch_size = config.get("embedding", {}).get("batch_size", 100)
    task_type_doc = config.get("embedding", {}).get("task_type_document", "RETRIEVAL_DOCUMENT")
    
    persist_dir = config.get("vector_store", {}).get("persist_directory", "./chroma_db")
    eval_dir = Path(PROJECT_ROOT / config.get("paths", {}).get("eval_data", "dev/data/eval"))
    
    print("=" * 60)
    print("🚀 MULAI PROSES EMBEDDING & VECTOR STORAGE")
    print(f"   Model       : {embed_model_name}")
    print(f"   Chroma DB   : {persist_dir}")
    print(f"   Eval Dir    : {eval_dir}")
    print("=" * 60)
    
    embedding_service = EmbeddingService(model_name=embed_model_name)
    vector_store = VectorStore(persist_directory=persist_dir)
    
    eval_dir.mkdir(parents=True, exist_ok=True)
    
    # Cari file chunks
    processed_dir = Path(PROJECT_ROOT / config.get("paths", {}).get("processed_data", "data/processed"))
    chunk_files = list(processed_dir.glob("chunks_*.json"))
    
    if not chunk_files:
        print(f"❌ Tidak ada file chunks di {processed_dir}. Jalankan run_ingestion.py terlebih dahulu.")
        sys.exit(1)
        
    all_chunks_for_eval = []
    
    for chunk_file in chunk_files:
        print(f"\n📄 Memproses: {chunk_file.name}")
        with open(chunk_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            
        if not chunks:
            print("   ⚠️ File kosong atau tidak valid.")
            continue
            
        print(f"   Meng-embed {len(chunks)} chunks...")
        texts = [c["content"] for c in chunks]
        
        # Generate Embeddings
        embeddings = embedding_service.embed_texts(texts, batch_size=embed_batch_size, task_type=task_type_doc)
        
        # Simpan ke Vector DB
        print("   Menyimpan ke Chroma DB...")
        vector_store.add_documents(chunks, embeddings)
        print("   ✅ Berhasil disimpan ke Chroma DB.")
        
        # Kumpulkan sample untuk evaluasi manual
        for c, emb in zip(chunks, embeddings):
            eval_record = {
                "chunk_id": c["chunk_id"],
                "source_file": c["source_file"],
                "content": c["content"],
                "embedding_sample": emb[:5] + ["... (truncated) ..."] + emb[-5:],
                "vector_dimension": len(emb)
            }
            all_chunks_for_eval.append(eval_record)

    # ==========================================
    # EKSPOR UNTUK EVALUASI / MONITORING MANUAL
    # ==========================================
    print(f"\n💾 Mengekspor data untuk evaluasi manual ke: {eval_dir}")
    
    # 1. Ekspor JSON lengkap (format evaluasi)
    json_export_path = eval_dir / "vector_store_export.json"
    with open(json_export_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks_for_eval, f, indent=2, ensure_ascii=False)
        
    # 2. Ekspor Markdown (agar mudah dibaca manusia / screenshot untuk laporan)
    md_export_path = eval_dir / "vector_store_sample.md"
    with open(md_export_path, "w", encoding="utf-8") as f:
        f.write("# Sample Data Vector Store (Chroma DB)\n\n")
        f.write(f"Total Chunks di Vector DB (dari run ini): **{len(all_chunks_for_eval)}**\n\n")
        f.write(f"Model Embedding: `{embed_model_name}`\n\n")
        f.write("---\n\n")
        
        # Tampilkan maksimal 5 sampel saja di Markdown
        for idx, record in enumerate(all_chunks_for_eval[:5]):
            f.write(f"### Sample {idx + 1}\n")
            f.write(f"- **Chunk ID**: `{record['chunk_id']}`\n")
            f.write(f"- **Source File**: `{record['source_file']}`\n")
            f.write(f"- **Vector Dimension**: `{record['vector_dimension']}`\n")
            f.write("- **Embedding Sample**: \n")
            f.write(f"  ```json\n  {json.dumps(record['embedding_sample'])}\n  ```\n")
            f.write("- **Content**:\n")
            f.write(f"> {record['content']}\n\n")
            f.write("---\n\n")
            
    print(f"   ✅ JSON Export : {json_export_path}")
    print(f"   ✅ MD Sample   : {md_export_path}")
    
    # Tampilkan stats akhir
    stats = vector_store.get_stats()
    print("\n" + "=" * 60)
    print("🏁 PROSES SELESAI")
    print(f"   Total Chunks di Chroma DB saat ini: {stats['total_chunks']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
