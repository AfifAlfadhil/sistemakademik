"""
pdf_extractor.py — Full OCR Pipeline untuk Ekstraksi Teks dari PDF

Semua halaman di-render ke gambar lalu di-OCR menggunakan Tesseract
dengan OpenCV preprocessing. Tipe halaman (teks/tabel/campuran)
dideteksi otomatis untuk memilih PSM yang optimal.
"""

import fitz  # PyMuPDF
import pytesseract
import shutil
import os
from PIL import Image
from pathlib import Path

# Inisialisasi konfigurasi path Tesseract untuk environment Railway / Nixpacks secara dinamis
if not shutil.which("tesseract"):
    found = False
    
    # 1. Cari di Nix store (Railway menggunakan Nixpacks)
    nix_store = Path("/nix/store")
    if nix_store.exists():
        try:
            tesseract_binaries = list(nix_store.glob("*-tesseract-*/bin/tesseract"))
            if tesseract_binaries:
                pytesseract.pytesseract.tesseract_cmd = str(tesseract_binaries[0])
                print(f"🔧 Pytesseract: Menemukan dan menggunakan binary dari Nix Store: {tesseract_binaries[0]}")
                found = True
        except Exception as e:
            print(f"⚠️ Gagal memindai Nix Store: {e}")
            
    # 2. Cari di jalur standard alternatif jika belum ditemukan
    if not found:
        alt_paths = [
            "/root/.nix-profile/bin/tesseract", 
            "/usr/bin/tesseract", 
            "/usr/local/bin/tesseract", 
            "/opt/homebrew/bin/tesseract"
        ]
        for path in alt_paths:
            if Path(path).exists():
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"🔧 Pytesseract: Menggunakan binary dari system path: {path}")
                found = True
                break
                
    if not found:
        print("⚠️ Tesseract binary tidak ditemukan di PATH, Nix Store, maupun jalur alternatif. Pastikan Tesseract sudah terinstal di OS.")

# Pastikan folder tessdata lokal ada, terisi model bahasa, dan TESSDATA_PREFIX terkonfigurasi
def ensure_tessdata():
    railway_tessdata = Path("/app/data/tessdata")
    local_tessdata = Path(__file__).resolve().parents[2] / "data" / "tessdata"
    
    tessdata_dir = railway_tessdata if railway_tessdata.parent.exists() else local_tessdata
    tessdata_dir.mkdir(parents=True, exist_ok=True)
    
    os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
    
    import urllib.request
    for lang in ["eng", "ind"]:
        file_path = tessdata_dir / f"{lang}.traineddata"
        if not file_path.exists():
            print(f"🔧 Downloading {lang}.traineddata to {file_path}...")
            try:
                urllib.request.urlretrieve(
                    f"https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata",
                    str(file_path)
                )
                print(f"✅ Successfully downloaded {lang}.traineddata")
            except Exception as e:
                print(f"❌ Failed to download {lang}.traineddata: {e}")

ensure_tessdata()

from src.config import config
from .image_preprocessing import preprocess_image_for_ocr, detect_page_type


def extract_pdf_full_ocr(
    pdf_path: str,
    dpi: int = None,
    tesseract_lang: str = None,
    psm_text: int = None,
    psm_table: int = None,
    psm_mixed: int = None,
    preprocessing_config: dict | None = None,
    log_callback = None,
) -> dict:
    ocr_config = config.get("ocr", {})
    dpi = dpi or ocr_config.get("dpi", 300)
    tesseract_lang = tesseract_lang or ocr_config.get("tesseract_lang", "ind")
    psm_text = psm_text or ocr_config.get("tesseract_psm_text", 6)
    psm_table = psm_table or ocr_config.get("tesseract_psm_table", 4)
    psm_mixed = psm_mixed or ocr_config.get("tesseract_psm_mixed", 3)
    preprocessing_config = preprocessing_config or ocr_config.get("preprocessing", None)

    """
    Ekstrak teks dari PDF menggunakan full OCR pipeline.
    
    Setiap halaman di-render ke gambar, di-preprocessing dengan OpenCV,
    lalu di-OCR dengan Tesseract menggunakan PSM yang sesuai tipe halaman.
    
    Args:
        pdf_path: Path ke file PDF
        dpi: Resolusi render (default 300)
        tesseract_lang: Bahasa Tesseract (default "ind" untuk Indonesia)
        psm_text: PSM mode untuk halaman teks (default 6)
        psm_table: PSM mode untuk halaman tabel (default 4)
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
        tesseract_config = f"--psm {psm} --oem 3"
        try:
            ocr_text = pytesseract.image_to_string(
                preprocessed,
                lang=tesseract_lang,
                config=tesseract_config,
            )
        except Exception as e:
            print(f"    ⚠️  OCR error pada {page_label}: {e}")
            ocr_text = ""

        # 6. Simpan hasil per halaman
        text_clean = ocr_text.strip()
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
