"""
run_ingestion.py — CLI Script untuk Ingest PDF ke Pipeline

Menjalankan pipeline lengkap:
  PDF → Render → Preprocess → OCR → Clean → Save .md → Chunk → Save .json

Usage:
  python dev/run_ingestion.py                    # Ingest semua PDF di dev/data/raw/
  python dev/run_ingestion.py path/to/file.pdf   # Ingest satu file spesifik
"""

import sys
import os
import json
import uuid
import time
from pathlib import Path

# Tambahkan root directory project ke sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

import yaml

from src.ingestion.pdf_extractor import extract_pdf_full_ocr
from src.ingestion.chunking import chunk_text


def load_config() -> dict:
    """Load konfigurasi dari config.yaml."""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        print("⚠️  config.yaml tidak ditemukan, menggunakan default")
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def ingest_single_pdf(pdf_path: Path, config: dict) -> dict:
    """
    Jalankan pipeline ingestion untuk satu file PDF.
    
    Returns:
        dict dengan summary hasil ingestion
    """
    filename = pdf_path.name
    document_id = str(uuid.uuid4())
    
    print(f"\n{'='*60}")
    print(f"📄 Processing: {filename}")
    print(f"   Document ID: {document_id}")
    print(f"{'='*60}")

    # === STEP 1: Full OCR Extraction ===
    print(f"\n🔍 Step 1: Full OCR Extraction...")
    start_time = time.time()

    ocr_config = config.get("ocr", {})
    preprocessing_config = ocr_config.get("preprocessing", {})

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
    page_count = extraction_result["page_count"]
    ocr_time = time.time() - start_time

    print(f"   ✅ OCR selesai: {len(raw_text)} chars, {page_count} halaman ({ocr_time:.1f}s)")

    # === STEP 2: Text Validation ===
    print(f"\n🧹 Step 2: Text Validation...")
    cleaned_text = raw_text
    chars_removed = 0
    print(f"   ✅ Text siap diproses ({len(cleaned_text)} chars)")

    # === STEP 3: Save Parsed Markdown ===
    print(f"\n💾 Step 3: Save Parsed Markdown...")
    processed_dir = Path(config.get("paths", {}).get("processed_data", "data/processed"))
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Bersihkan nama file untuk output
    safe_name = pdf_path.stem
    md_path = processed_dir / f"parsed_{safe_name}.md"
    md_path.write_text(cleaned_text, encoding="utf-8")
    print(f"   ✅ Saved: {md_path}")

    # === STEP 4: Chunking ===
    print(f"\n✂️  Step 4: Chunking...")
    chunking_config = config.get("ingestion", {})

    chunks = chunk_text(
        text=cleaned_text,
        source_file=filename,
        document_id=document_id,
        chunk_size=chunking_config.get("chunk_size", 1000),
        chunk_overlap=chunking_config.get("chunk_overlap", 150),
        separators=chunking_config.get("separators"),
    )

    avg_chunk_size = sum(c["char_count"] for c in chunks) / len(chunks) if chunks else 0
    print(f"   ✅ {len(chunks)} chunks created (avg {avg_chunk_size:.0f} chars)")

    # === STEP 5: Save Chunks JSON ===
    print(f"\n💾 Step 5: Save Chunks JSON...")
    json_path = processed_dir / f"chunks_{safe_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"   ✅ Saved: {json_path}")

    # === Summary ===
    summary = {
        "document_id": document_id,
        "filename": filename,
        "page_count": page_count,
        "raw_chars": len(raw_text),
        "cleaned_chars": len(cleaned_text),
        "chunk_count": len(chunks),
        "avg_chunk_size": round(avg_chunk_size),
        "ocr_time_seconds": round(ocr_time, 1),
        "pages_detail": extraction_result["pages"],
        "output_files": {
            "markdown": str(md_path),
            "chunks": str(json_path),
        },
    }

    return summary


def main():
    """Entry point CLI."""
    config = load_config()

    # Tentukan file yang akan diproses
    if len(sys.argv) > 1:
        # Proses file spesifik
        pdf_files = [Path(sys.argv[1])]
        for f in pdf_files:
            if not f.exists():
                print(f"❌ File tidak ditemukan: {f}")
                sys.exit(1)
            if f.suffix.lower() != ".pdf":
                print(f"❌ Bukan file PDF: {f}")
                sys.exit(1)
    else:
        # Proses semua PDF di data/raw/
        raw_dir = Path(config.get("paths", {}).get("raw_data", "data/raw"))
        if not raw_dir.exists():
            print(f"❌ Direktori tidak ditemukan: {raw_dir}")
            sys.exit(1)

        pdf_files = sorted(raw_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"❌ Tidak ada file PDF di {raw_dir}")
            sys.exit(1)

    print(f"🚀 Ingestion Pipeline")
    print(f"   Files to process: {len(pdf_files)}")
    print(f"   Config: chunk_size={config.get('ingestion', {}).get('chunk_size', 1000)}, "
          f"overlap={config.get('ingestion', {}).get('chunk_overlap', 150)}")
    print(f"   OCR: Tesseract (lang={config.get('ocr', {}).get('tesseract_lang', 'ind')}, "
          f"dpi={config.get('ocr', {}).get('dpi', 300)})")

    # Proses setiap PDF
    total_start = time.time()
    all_summaries = []

    for pdf_file in pdf_files:
        try:
            summary = ingest_single_pdf(pdf_file, config)
            all_summaries.append(summary)
        except Exception as e:
            print(f"\n❌ Error processing {pdf_file.name}: {e}")
            import traceback
            traceback.print_exc()
            all_summaries.append({
                "filename": pdf_file.name,
                "error": str(e),
            })

    total_time = time.time() - total_start

    # Save pipeline summary
    processed_dir = Path(config.get("paths", {}).get("processed_data", "data/processed"))
    processed_dir.mkdir(parents=True, exist_ok=True)
    summary_path = processed_dir / "pipeline_summary.json"
    pipeline_summary = {
        "total_documents": len(pdf_files),
        "successful": sum(1 for s in all_summaries if "error" not in s),
        "failed": sum(1 for s in all_summaries if "error" in s),
        "total_chunks": sum(s.get("chunk_count", 0) for s in all_summaries),
        "total_time_seconds": round(total_time, 1),
        "documents": all_summaries,
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(pipeline_summary, f, ensure_ascii=False, indent=2)

    # Print final summary
    print(f"\n{'='*60}")
    print(f"🏁 Pipeline Complete!")
    print(f"{'='*60}")
    print(f"   Documents: {pipeline_summary['successful']}/{pipeline_summary['total_documents']} successful")
    print(f"   Total chunks: {pipeline_summary['total_chunks']}")
    print(f"   Total time: {total_time:.1f}s")
    print(f"   Summary saved: {summary_path}")

    for s in all_summaries:
        if "error" not in s:
            print(f"\n   📄 {s['filename']}")
            print(f"      Pages: {s['page_count']} | Chars: {s['cleaned_chars']} | Chunks: {s['chunk_count']}")
            print(f"      📝 {s['output_files']['markdown']}")
        else:
            print(f"\n   ❌ {s['filename']}: {s['error']}")


if __name__ == "__main__":
    main()
