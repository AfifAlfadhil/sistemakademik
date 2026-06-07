"""
cleaning.py — Text Normalization & Garbage Filtering

Membersihkan teks hasil OCR dari artefak:
- Null bytes dan karakter kontrol
- Hyphenation lintas baris
- Garbage text dari stempel/tanda tangan
- Nomor halaman dan watermark
- Whitespace berlebihan
"""

import re


def clean_extracted_text(text: str) -> str:
    """
    Pipeline cleaning lengkap untuk teks hasil OCR.
    
    Args:
        text: Raw text dari OCR
    
    Returns:
        Teks yang sudah dibersihkan
    """
    if not text or not text.strip():
        return ""

    # 1. Basic normalization
    text = text.replace('\xa0', ' ')   # non-breaking space
    text = text.replace('\x00', '')     # null bytes
    text = re.sub(r'\r\n', '\n', text)  # normalize line endings
    text = re.sub(r'\r', '\n', text)

    # 2. Fix hyphenation lintas baris (kata terpotong di akhir baris)
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

    # 3. Filter garbage text dari stempel/tanda tangan/grafis
    text = _filter_garbage_text(text)

    # 4. Remove common scan artifacts
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)  # page numbers: -1-
    text = re.sub(r'^\s*SALINAN\s*$', '', text, flags=re.MULTILINE)       # watermark
    text = re.sub(r'^\s*ttd\.?\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)  # "ttd."

    # 4b. Clean Table of Contents dot leaders hallucination
    text = _clean_toc_leaders(text)

    # 5. Collapse excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)   # max 2 newlines
    text = re.sub(r' {2,}', ' ', text)        # max 1 space

    # 6. Trim whitespace per baris
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    # 7. Remove leading/trailing empty lines
    text = text.strip()

    return text


def _filter_garbage_text(text: str) -> str:
    """
    Hapus baris yang kemungkinan besar hasil OCR dari area stempel,
    tanda tangan, atau elemen grafis non-teks.
    """
    cleaned_lines = []

    for line in text.split('\n'):
        stripped = line.strip()

        # Skip baris kosong — pertahankan sebagai separator
        if not stripped:
            cleaned_lines.append(line)
            continue

        # Skip baris terlalu pendek (< 3 karakter non-whitespace)
        if len(stripped) < 3:
            continue

        # Hitung rasio karakter alfanumerik + spasi vs total
        alnum_space = sum(1 for c in stripped if c.isalnum() or c.isspace() or c in '.,;:()/-')
        ratio = alnum_space / len(stripped) if len(stripped) > 0 else 0

        if ratio < 0.5:
            # Terlalu banyak karakter aneh → kemungkinan OCR garbage
            continue

        # Deteksi baris dengan terlalu banyak kata 1-2 huruf berurutan
        # Indikator OCR garbage dari stempel/grafis
        words = stripped.split()
        if len(words) > 4:
            short_words = sum(1 for w in words if len(w) <= 2)
            if short_words / len(words) > 0.65:
                continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def _clean_toc_leaders(text: str) -> str:
    """Bersihkan OCR garbage dari dot leaders Daftar Isi (TOC)."""
    cleaned_lines = []
    
    # Karakter yang biasa muncul sebagai noise saat Tesseract membaca baris titik-titik
    garbage_chars = set('oWc#nmaA»”rXkTeNlBKG')
    
    for line in text.split('\n'):
        # Cari pola dot leader `..` atau `...`
        match = re.search(r'\.{2,}', line)
        if match:
            # Teks sebelum titik-titik
            prefix = line[:match.start()]
            # Teks setelah titik-titik (sampai akhir baris)
            suffix = line[match.start():]
            
            # Abaikan spasi dan titik untuk mengevaluasi teks
            chars_only = [c for c in suffix if c not in ' .\t']
            
            if chars_only:
                garbage_count = sum(1 for c in chars_only if c in garbage_chars)
                ratio = garbage_count / len(chars_only)
                
                # Cek juga apakah ada pola berulang (misal: oooo, nnnn)
                has_repeating = bool(re.search(r'(.)\1{3,}', suffix))
                
                # Jika rasio garbage tinggi ATAU ada karakter berulang
                if ratio > 0.5 or has_repeating:
                    # Ambil angka halaman di paling belakang (jika ada)
                    page_match = re.search(r'(\d{1,3})\s*$', suffix)
                    page_num = f" {page_match.group(1)}" if page_match else ""
                    
                    line = prefix + page_num
        
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)
