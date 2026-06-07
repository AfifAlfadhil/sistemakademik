# Changelog

Dokumen ini mencatat seluruh perubahan, perombakan metode, dan peningkatan fungsionalitas dari versi sebelumnya (*Legacy*) menuju arsitektur yang baru dan jauh lebih optimal.

## [Unreleased] - Rombak Total Arsitektur Ingestion & Vector Store

### Mengapa Perombakan Ini Dilakukan?
Arsitektur sebelumnya memiliki keterbatasan dalam membaca dokumen yang memuat gambar/tabel (hanya mengandalkan `pdfplumber` biasa), pemrosesan yang lambat akibat menjalankan model *embedding* secara lokal, serta kurangnya modularitas antara sistem *back-office* (skrip pemroses data) dengan sistem aplikasi (*source code*). Rilis ini menuntaskan masalah tersebut.

### Ditambahkan (Added)
- **Ekstraksi PDF dengan OCR Tingkat Lanjut (`src/ingestion/`)**: 
  - **Metode Lama**: Hanya menggunakan teks mentah.
  - **Metode Baru**: Menggabungkan `PyMuPDF` untuk mendeteksi teks asli dan `pytesseract` (Tesseract OCR) bersama `OpenCV` untuk mendeteksi teks di dalam gambar dan membedah tabel. Parameter *Computer Vision* (seperti `deskew`, `adaptive_threshold`) kini dikontrol langsung dari `config.yaml`.
- **Chunking Semantik**: Teks kini dipotong menggunakan `langchain-text-splitters` dengan `chunk_size` 1000 dan `overlap` 150. Jauh lebih aman untuk menjaga keutuhan konteks antar kalimat.
- **Isolasi Environment (`.env`)**: Memasukkan pustaka `python-dotenv` agar *API Key* tidak pernah bocor ke dalam *source code*.

### Diubah (Changed)
- **Metode Embedding (Lokal ➡️ Cloud)**:
  - **Metode Lama**: Menjalankan model `sentence-transformers/LaBSE` secara lokal (memakan memori besar dan lambat).
  - **Metode Baru**: Beralih sepenuhnya ke **Google Gemini API** (`text-embedding-004` / `gemini-embedding-2`). Menghasilkan vektor berdimensi tinggi (3072 dimensi) dengan sangat cepat, mendukung *batch processing* massal.
- **Struktur Direktori (Separation of Concerns)**:
  - Kode inti diletakkan ke dalam `/src/` (sebagai modul mandiri).
  - Skrip eksekusi harian (*Runner* untuk ekstraksi & *embedding*) dipindahkan ke `/dev/`. Logika eksekusi data tidak lagi tercampur di luar atau *root*.
- **Manajemen Konfigurasi Terpusat (`config.yaml`)**: Seluruh nilai yang sebelumnya di-*hardcode* di dalam Python kini ditarik dari satu file YAML.
- **Pembaruan `requirements.txt` & Persiapan Masa Depan**: Mengganti daftar library sepenuhnya. **Penting:** Beberapa paket di `requirements.txt` (seperti `fastapi`, `uvicorn`, `aiosqlite`) dan parameter di `config.yaml` (seperti `llm` dan `chat`) telah disiapkan dan di-*comment out*. Ini sengaja dirancang sebagai **kerangka cetak biru (blueprint)** yang akan langsung digunakan pada fase pengembangan berikutnya, sehingga proyek tidak perlu merancang *config* baru dari awal.

### Dihapus (Removed)
- Menghapus pustaka lawas yang tidak efisien seperti `pdfplumber` dan `sentence-transformers`.
- Menghapus skrip tunggal (`run_ingestion.py` di luar) dan folder lama (`parser.py`, `chunker.py`, `metadata_tagger.py`) yang metodenya sudah tertinggal.
