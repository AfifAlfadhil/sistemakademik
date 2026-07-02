"""
pdf_extractor.py — Full OCR Pipeline untuk Ekstraksi Teks dari PDF

Semua halaman di-render ke gambar lalu di-OCR menggunakan Tesseract
dengan OpenCV preprocessing. Tipe halaman (teks/tabel/campuran)
dideteksi otomatis untuk memilih PSM yang optimal.
"""

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pathlib import Path

from .image_preprocessing import preprocess_image_for_ocr, detect_page_type
from .cleaning import clean_extracted_text

def extract_pdf_full_ocr( 
    pdf_path: str,
    dpi: int = 400,
    tesseract_lang: str = "ind",
    psm_text: int = 6,
    psm_table: int = 11,
    psm_mixed: int = 3,
    preprocessing_config: dict | None = None,
    log_callback = None,
) -> dict:
    """
    Ekstrak teks dari PDF menggunakan full OCR pipeline.
    
    Setiap halaman di-render ke gambar, di-preprocessing dengan OpenCV,
    lalu di-OCR dengan Tesseract menggunakan PSM yang sesuai tipe halaman.
    
    Args:
        pdf_path: Path ke file PDF
        dpi: Resolusi render (default 400)
        tesseract_lang: Bahasa Tesseract (default "ind" untuk Indonesia)
        psm_text: PSM mode untuk halaman teks (default 6)
        psm_table: PSM mode untuk halaman tabel (default 11)
        psm_mixed: PSM mode untuk halaman campuran (default 3)
        preprocessing_config: Override parameter preprocessing OpenCV
    
    Returns:
        dict dengan keys:
            - "text": teks hasil OCR gabungan semua halaman
            - "page_count": jumlah halaman
            - "pages": list detail per halaman
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File PDF tidak ditemukan: {pdf_path}")

    preprocess_params = preprocessing_config or {}

    doc = fitz.open(str(pdf_path))
    pages_result = []
    all_text_parts = []

    print(f"  📄 Memproses {len(doc)} halaman...")

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_label = f"Halaman {page_num + 1}/{len(doc)}"

        # 1. Render halaman ke gambar
        pix = page.get_pixmap(dpi=dpi)
        pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # 2. Deteksi tipe halaman
        page_type = detect_page_type(pil_image)

        # 3. Pilih PSM berdasarkan tipe halaman
        if page_type == "table":
            psm = psm_table
        elif page_type == "mixed":
            psm = psm_mixed
        else:
            psm = psm_text

        # 4. Preprocessing gambar dengan OpenCV
        preprocessed = preprocess_image_for_ocr(pil_image, **preprocess_params)

        # 5. OCR dengan Tesseract
        tesseract_config = (
            f"--oem 3 " 
            f"--psm {psm} " 
            "-c preserve_interword_spaces=1"
            "-c textord_heavy_nr=1"
        )
        try:
            ocr_text = pytesseract.image_to_string(
                preprocessed,
                lang=tesseract_lang,
                config=tesseract_config,
            )

            best_text = ocr_text
            best_psm = psm
            
            # fallback untuk teks yang terlalu sedikit
            if len(ocr_text.strip()) < 100:
                if page_type == "table":
                    fallback_psms = [6, 11, 12]
                else:
                    fallback_psms = [11]
                
                for fallback_psm in fallback_psms:
                    if fallback_psm == psm:
                        continue
                    
                    fallback_config = ( 
                    f"--oem 3" 
                    f"--psm {fallback_psm}"
                    "-c preserve_interword_spaces=1"
                )

                candidate = pytesseract.image_to_string(preprocessed, lang=tesseract_lang, config=fallback_config,)
                if len(candidate.strip()) > len(best_text.strip()):
                    best_text = candidate
                    best_psm = fallback_psm

            ocr_text = best_text
            psm = best_psm

        except Exception as e:
            print(f"    ⚠️  OCR error pada {page_label}: {e}")
            ocr_text = ""

        # 6. Simpan hasil per halaman
        text_clean = clean_extracted_text(ocr_text)
        char_count = len(text_clean)

        pages_result.append({
            "page_num": page_num + 1,
            "page_type": page_type,
            "psm_used": psm,
            "char_count": char_count,
        })

        if text_clean:
            all_text_parts.append(text_clean)

        status_icon = "✅" if char_count > 50 else "⚠️ " if char_count > 0 else "❌"
        log_msg = f"{status_icon} {page_label}: {page_type} (PSM {psm}) → {char_count} chars"
        print(f"    {log_msg}")
        if log_callback:
            log_callback(log_msg)

    page_count = len(doc)
    doc.close()

    # Gabung semua halaman
    full_text = "\n\n".join(all_text_parts)

    return {
        "text": full_text,
        "page_count": page_count,
        "pages": pages_result,
    }
