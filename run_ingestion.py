"""
run_ingestion.py — Pipeline Ingestion Lengkap (Markdown-First)

Script ini menjalankan seluruh proses parsing dokumen PDF ke Markdown:
1. Parse semua PDF dari data/raw/ menjadi .md di data/processed/
2. Ekstrak metadata dokumen
3. Chunking berdasarkan header Markdown (# BAB, ## Pasal)
4. Enrichment metadata per chunk
5. Simpan hasil chunk ke data/processed/chunks_all.json

Penggunaan:
    python run_ingestion.py
    python run_ingestion.py --pdf-dir data/raw --output-dir data/processed
"""

import json
import sys
import argparse
import glob
from pathlib import Path
from datetime import datetime

# Tambahkan root project ke path
sys.path.insert(0, str(Path(__file__).parent))

import yaml
from src.ingestion.parser import parse_legal_pdf_to_markdown, extract_document_metadata
from src.ingestion.chunker import chunk_markdown
from src.ingestion.metadata_tagger import enrich_chunk_metadata


def load_config(config_path: str = "config.yaml") -> dict:
    """Load konfigurasi dari file YAML."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_ingestion_pipeline(
    pdf_dir: str = "data/raw",
    output_dir: str = "data/processed",
    chunk_max_size: int = 1500,
    chunk_overlap: int = 200,
    verbose: bool = True
) -> dict:
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = Path(pdf_dir)

    start_time = datetime.now()

    print("=" * 70)
    print("🚀 PIPELINE INGESTION DOKUMEN JDIH UNS (MARKDOWN-FIRST)")
    print(f"   Waktu mulai : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   PDF dir     : {pdf_dir}")
    print(f"   Output dir  : {output_dir}")
    print(f"   Max Chunk   : {chunk_max_size} (overlap: {chunk_overlap})")
    print("=" * 70)

    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ Tidak ada file PDF ditemukan di direktori {pdf_dir}")
        return {}

    all_metadata = []
    all_chunks = []
    total_chars = 0

    # ========================================================================
    # STEP 1 & 2: Parsing PDF ke Markdown & Chunking
    # ========================================================================
    print("\n" + "─" * 70)
    print("📄 STEP 1 & 2: Parsing PDF ke Markdown & Pemotongan (Chunking)")
    print("─" * 70)

    for pdf_path in pdf_files:
        filename = pdf_path.name
        if verbose:
            print(f"\nMemproses: {filename}...")
            
        # Parse PDF -> Markdown (Tabel juga diekstrak di sini)
        md_text = parse_legal_pdf_to_markdown(str(pdf_path))
        total_chars += len(md_text)
        
        # Simpan file markdown penuh untuk referensi
        md_filename = f"parsed_{filename.replace('.pdf', '')}.md"
        md_filepath = output_dir / md_filename
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(md_text)
            
        if verbose:
            print(f"  ✅ Tersimpan sebagai: {md_filename} ({len(md_text):,} karakter)")

        # Ekstrak metadata tingkat dokumen
        metadata = extract_document_metadata(md_text, filename)
        all_metadata.append(metadata)

        # Chunking Markdown by Headers (# BAB, ## Pasal)
        chunks = chunk_markdown(md_text, metadata, chunk_max_size, chunk_overlap)
        # Enrich chunks immediately for this document
        enriched_chunks = enrich_chunk_metadata(chunks)
        
        # Simpan chunks yang sudah diperkaya per file
        chunk_filename = f"chunks_{filename.replace('.pdf', '')}.json"
        chunk_filepath = output_dir / chunk_filename
        with open(chunk_filepath, "w", encoding="utf-8") as f:
            json.dump(enriched_chunks, f, ensure_ascii=False, indent=2)
            
        all_chunks.extend(enriched_chunks)
        
        if verbose:
            print(f"  ✂️ Menghasilkan {len(enriched_chunks)} enriched chunks (tersimpan di {chunk_filename})")

    # Simpan metadata dokumen (hanya metadata tingkat dokumen)
    metadata_path = output_dir / "document_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Metadata keseluruhan dokumen disimpan ke: {metadata_path}")

    # ========================================================================
    # RINGKASAN AKHIR
    # ========================================================================
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    summary = {
        "pipeline_run": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "config": {
                "chunk_max_size": chunk_max_size,
                "chunk_overlap": chunk_overlap,
                "pdf_dir": str(pdf_dir),
                "output_dir": str(output_dir),
            },
        },
        "documents": {
            "total_processed": len(pdf_files)
        },
        "chunks": {
            "total_chunks": len(all_chunks),
            "total_chars": sum(len(c["text"]) for c in all_chunks),
            "average_chars": round(sum(len(c["text"]) for c in all_chunks) / max(1, len(all_chunks))),
            "with_numeric_data": sum(1 for c in all_chunks if c["metadata"].get("contains_numeric_data")),
            "with_cross_reference": sum(1 for c in all_chunks if c["metadata"].get("has_cross_reference")),
            "avg_importance_score": round(sum(c["metadata"].get("importance_score", 0) for c in all_chunks) / max(1, len(all_chunks)), 3)
        },
        "content_categories": {}
    }

    # Distribusi Kategori
    for c in all_chunks:
        cat = c["metadata"].get("content_category", "lainnya")
        summary["content_categories"][cat] = summary["content_categories"].get(cat, 0) + 1

    summary_path = output_dir / "pipeline_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("✅ PIPELINE INGESTION SELESAI!")
    print("=" * 70)
    print(f"\n📋 Ringkasan:")
    print(f"   Dokumen diproses  : {summary['documents']['total_processed']}")
    print(f"   Total chunks      : {summary['chunks']['total_chunks']}")
    print(f"   Total karakter    : {summary['chunks']['total_chars']:,}")
    print(f"   Rata-rata chunk   : {summary['chunks']['average_chars']} karakter")
    print(f"   Waktu eksekusi    : {summary['pipeline_run']['duration_seconds']} detik")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Ingestion Dokumen JDIH UNS (Markdown-First)"
    )
    parser.add_argument(
        "--pdf-dir", default="data/raw",
        help="Direktori berisi file PDF sumber (default: data/raw)"
    )
    parser.add_argument(
        "--output-dir", default="data/processed",
        help="Direktori output (default: data/processed)"
    )
    parser.add_argument(
        "--chunk-max-size", type=int, default=None,
        help="Ukuran chunk maksimal sebelum di-split paksa (override config.yaml)"
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=None,
        help="Overlap chunk sekunder (override config.yaml)"
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path ke file konfigurasi (default: config.yaml)"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Kurangi output verbose"
    )

    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"⚠️  Config file '{args.config}' tidak ditemukan, menggunakan defaults")
        config = {"chunking": {"chunk_size": 1500, "chunk_overlap": 200}}

    chunk_size = args.chunk_max_size or config["chunking"].get("chunk_size", 1500)
    chunk_overlap = args.chunk_overlap or config["chunking"].get("chunk_overlap", 200)

    run_ingestion_pipeline(
        pdf_dir=args.pdf_dir,
        output_dir=args.output_dir,
        chunk_max_size=chunk_size,
        chunk_overlap=chunk_overlap,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
