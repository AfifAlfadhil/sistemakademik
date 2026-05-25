"""
metadata_tagger.py — Enrichment Metadata untuk Chunks Dokumen Hukum

Modul ini bertanggung jawab untuk:
1. Memperkaya metadata chunk dengan informasi kontekstual tambahan
2. Mendeteksi kategori konten (definisi, ketentuan, sanksi, dll)
3. Mengidentifikasi istilah-istilah khusus (singkatan, akronim)
4. Menambahkan tag untuk pencarian dan filtering
"""

import re
from typing import Optional


# Daftar singkatan/akronim umum dalam dokumen JDIH UNS
LEGAL_ABBREVIATIONS = {
    "UKT": "Uang Kuliah Tunggal",
    "BKT": "Biaya Kuliah Tunggal",
    "IPI": "Iuran Pengembangan Institusi",
    "UNS": "Universitas Sebelas Maret",
    "IKN": "Ibu Kota Nusantara",
    "MWA": "Majelis Wali Amanat",
    "KIP-K": "Kartu Indonesia Pintar Kuliah",
    "SPI": "Sumbangan Pengembangan Institusi",
    "SPP": "Sumbangan Pembinaan Pendidikan",
    "NIM": "Nomor Induk Mahasiswa",
    "PBB": "Pajak Bumi dan Bangunan",
    "STNK": "Surat Tanda Nomor Kendaraan",
    "Perrek": "Peraturan Rektor",
    "SK": "Surat Keputusan",
}

# Kategori konten yang mungkin ada dalam chunk
CONTENT_CATEGORIES = {
    "definisi": [
        r"yang\s+selanjutnya\s+disebut",
        r"yang\s+selanjutnya\s+disingkat",
        r"adalah\s+",
        r"yang\s+dimaksud\s+dengan",
    ],
    "ketentuan_umum": [
        r"KETENTUAN\s+UMUM",
        r"Dalam\s+Peraturan\s+(?:Rektor\s+)?ini",
    ],
    "penetapan": [
        r"ditetapkan\s+(?:oleh\s+)?(?:Rektor|Dekan)",
        r"Rektor\s+menetapkan",
        r"besaran\s+.*?ditetapkan",
    ],
    "keringanan": [
        r"keringanan",
        r"pengurangan",
        r"pembebasan",
        r"potongan",
    ],
    "sanksi": [
        r"sanksi",
        r"denda",
        r"penalti",
        r"dikenakan",
    ],
    "prosedur": [
        r"tata\s+cara",
        r"prosedur",
        r"mekanisme",
        r"tahapan",
        r"mengajukan\s+permohonan",
    ],
    "pembayaran": [
        r"pembayaran",
        r"cicilan",
        r"angsuran",
        r"tagihan",
        r"tarif",
    ],
    "ketentuan_peralihan": [
        r"KETENTUAN\s+PERALIHAN",
        r"tetap\s+berlaku",
        r"masih\s+berlaku",
    ],
    "ketentuan_penutup": [
        r"KETENTUAN\s+PENUTUP",
        r"mulai\s+berlaku",
        r"ditetapkan\s+di",
        r"diundangkan",
    ],
    "ruang_lingkup": [
        r"RUANG\s+LINGKUP",
        r"mengatur\s+tentang",
        r"berlaku\s+untuk",
    ],
}


def _detect_content_category(text: str) -> list[str]:
    """
    Deteksi kategori konten dari teks chunk.

    Args:
        text: Teks chunk

    Returns:
        List of kategori yang terdeteksi
    """
    categories = []
    text_lower = text.lower()

    for category, patterns in CONTENT_CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, text_lower if category not in [
                "ketentuan_umum", "ketentuan_peralihan", "ketentuan_penutup"
            ] else text):
                categories.append(category)
                break  # Satu pattern match cukup per kategori

    return categories


def _detect_abbreviations(text: str) -> dict:
    """
    Deteksi singkatan/akronim yang muncul dalam chunk.

    Args:
        text: Teks chunk

    Returns:
        Dict mapping singkatan → kepanjangan
    """
    found = {}
    for abbrev, full_form in LEGAL_ABBREVIATIONS.items():
        if abbrev in text:
            found[abbrev] = full_form
    return found


def _detect_key_terms(text: str) -> list[str]:
    """
    Deteksi istilah-istilah kunci dalam chunk.

    Args:
        text: Teks chunk

    Returns:
        List of istilah kunci yang ditemukan
    """
    key_terms = []

    # Istilah pendidikan
    education_terms = [
        "program sarjana", "program magister", "program doktor",
        "program diploma", "program profesi", "program vokasi",
        "sarjana terapan", "magister terapan",
        "semester", "tahun akademik", "kurikulum",
        "beasiswa", "mahasiswa asing", "kelas internasional",
        "seleksi mandiri", "seleksi nasional",
    ]

    # Istilah biaya
    financial_terms = [
        "uang kuliah tunggal", "biaya kuliah tunggal",
        "iuran pengembangan institusi", "biaya pendidikan",
        "cicilan", "keringanan", "pembebasan",
        "pengembalian", "kelebihan pembayaran",
    ]

    text_lower = text.lower()
    for term in education_terms + financial_terms:
        if term in text_lower:
            key_terms.append(term)

    return key_terms


def _calculate_chunk_importance(chunk: dict) -> float:
    """
    Hitung skor kepentingan chunk (0.0 - 1.0).

    Chunk yang berisi definisi, ketentuan utama, atau besaran angka
    biasanya lebih penting untuk QA system.

    Args:
        chunk: Dict chunk dengan metadata

    Returns:
        Float skor kepentingan (0.0 - 1.0)
    """
    score = 0.5  # Base score

    text = chunk["text"]
    categories = chunk["metadata"].get("content_categories", [])

    # Bonus untuk chunk definisi (penting untuk pemahaman)
    if "definisi" in categories:
        score += 0.2

    # Bonus untuk chunk yang berisi angka/besaran (sering ditanyakan)
    if re.search(r'Rp\s*[\d.,]+|rupiah|\d+\.\d{3}', text, re.IGNORECASE):
        score += 0.15

    # Bonus untuk chunk penetapan (berisi keputusan konkret)
    if "penetapan" in categories:
        score += 0.1

    # Bonus untuk chunk prosedur (berisi tata cara)
    if "prosedur" in categories:
        score += 0.1

    # Bonus untuk chunk yang memiliki nomor Pasal eksplisit
    if chunk["metadata"].get("pasal"):
        score += 0.05

    # Penalti untuk chunk pembuka/penutup yang kurang informatif
    if "ketentuan_penutup" in categories:
        score -= 0.15
    if chunk["metadata"].get("chunk_index", 0) == 0:
        # Chunk pertama biasanya header dokumen
        score -= 0.1

    return min(max(score, 0.0), 1.0)  # Clamp to [0, 1]


def enrich_chunk_metadata(chunks: list[dict]) -> list[dict]:
    """
    Perkaya metadata setiap chunk dengan informasi tambahan.

    Informasi yang ditambahkan:
    - content_categories: Kategori konten (definisi, penetapan, dll)
    - abbreviations: Singkatan yang muncul
    - key_terms: Istilah kunci
    - importance_score: Skor kepentingan (0.0 - 1.0)
    - has_numeric_data: Apakah berisi data numerik
    - has_cross_reference: Apakah berisi referensi silang

    Args:
        chunks: List of chunk dicts

    Returns:
        List of chunk dicts yang sudah diperkaya metadata-nya
    """
    enriched_chunks = []

    for chunk in chunks:
        text = chunk["text"]

        # 1. Deteksi kategori konten
        categories = _detect_content_category(text)
        chunk["metadata"]["content_categories"] = categories

        # 2. Deteksi singkatan
        abbreviations = _detect_abbreviations(text)
        chunk["metadata"]["abbreviations_found"] = list(abbreviations.keys())

        # 3. Deteksi istilah kunci
        key_terms = _detect_key_terms(text)
        chunk["metadata"]["key_terms"] = key_terms

        # 4. Deteksi apakah berisi data numerik (besaran biaya, persentase)
        has_numeric = bool(re.search(
            r'Rp\s*[\d.,]+|\d+%|\d+\.\d{3}|kelompok\s+[IVX]+',
            text, re.IGNORECASE
        ))
        chunk["metadata"]["has_numeric_data"] = has_numeric

        # 5. Deteksi apakah berisi referensi silang
        has_cross_ref = bool(chunk["metadata"].get("cross_references"))
        chunk["metadata"]["has_cross_reference"] = has_cross_ref

        # 6. Hitung skor kepentingan
        importance = _calculate_chunk_importance(chunk)
        chunk["metadata"]["importance_score"] = round(importance, 3)

        # 7. Buat ringkasan lokasi dalam dokumen
        location_parts = []
        if chunk["metadata"].get("bab"):
            location_parts.append(f"BAB {chunk['metadata']['bab']}")
        if chunk["metadata"].get("bagian"):
            location_parts.append(f"Bagian {chunk['metadata']['bagian']}")
        if chunk["metadata"].get("pasal"):
            location_parts.append(f"Pasal {chunk['metadata']['pasal']}")
        if chunk["metadata"].get("ayat_list"):
            ayat_str = ", ".join(
                [f"({a})" for a in chunk["metadata"]["ayat_list"][:3]]
            )
            location_parts.append(f"Ayat {ayat_str}")

        chunk["metadata"]["location_label"] = " > ".join(location_parts) if location_parts else "Header/Pembukaan"

        enriched_chunks.append(chunk)

    # Statistik enrichment
    cat_counts = {}
    for c in enriched_chunks:
        for cat in c["metadata"]["content_categories"]:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    has_numeric_count = sum(
        1 for c in enriched_chunks if c["metadata"]["has_numeric_data"]
    )
    has_cross_ref_count = sum(
        1 for c in enriched_chunks if c["metadata"]["has_cross_reference"]
    )

    print(f"\n🏷️  Metadata Enrichment selesai:")
    print(f"   Total chunks diperkaya: {len(enriched_chunks)}")
    print(f"   Chunks dengan data numerik: {has_numeric_count}")
    print(f"   Chunks dengan referensi silang: {has_cross_ref_count}")
    print(f"\n   Distribusi Kategori Konten:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"     {cat}: {count} chunks")

    # Distribusi skor kepentingan
    scores = [c["metadata"]["importance_score"] for c in enriched_chunks]
    print(f"\n   Skor Kepentingan:")
    print(f"     Rata-rata: {sum(scores) / len(scores):.3f}")
    print(f"     Tertinggi: {max(scores):.3f}")
    print(f"     Terendah : {min(scores):.3f}")

    return enriched_chunks


if __name__ == "__main__":
    """Quick test metadata enrichment."""
    import json

    # Load chunks yang sudah ada
    try:
        with open("data/processed/chunks_all.json", "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except FileNotFoundError:
        print("❌ File chunks_all.json belum ada. Jalankan chunker.py terlebih dahulu.")
        exit(1)

    # Enrich
    enriched = enrich_chunk_metadata(chunks)

    # Simpan
    output_path = "data/processed/chunks_enriched.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Enriched chunks disimpan ke: {output_path}")

    # Preview
    print(f"\n{'=' * 60}")
    print("PREVIEW ENRICHED CHUNK")
    print(f"{'=' * 60}")
    for chunk in enriched[:2]:
        print(f"\n--- {chunk['id']} ---")
        print(f"Lokasi    : {chunk['metadata']['location_label']}")
        print(f"Kategori  : {chunk['metadata']['content_categories']}")
        print(f"Singkatan : {chunk['metadata']['abbreviations_found']}")
        print(f"Istilah   : {chunk['metadata']['key_terms']}")
        print(f"Numerik   : {chunk['metadata']['has_numeric_data']}")
        print(f"Cross-ref : {chunk['metadata']['has_cross_reference']}")
        print(f"Importance: {chunk['metadata']['importance_score']}")
        print(f"Text (200 chars): {chunk['text'][:200]}...")
