# SAKA — Sistem Asisten Kampus UNS

SAKA (*Sistem Asisten Kampus UNS*) adalah chatbot akademik berbasis **Retrieval-Augmented Generation (RAG)** yang dirancang untuk membantu mahasiswa S1 Universitas Sebelas Maret (UNS) memperoleh informasi akademik berdasarkan dokumen resmi universitas.  

Sistem ini memadukan kekuatan *Large Language Model* (LLM) dengan *knowledge base* spesifik dari dokumen-dokumen kampus untuk menghasilkan jawaban yang sangat relevan, faktual, *to-the-point*, dan bebas dari halusinasi kecerdasan buatan.

---

## 🎯 Cakupan Sistem

Sistem SAKA dirancang secara khusus untuk menjawab berbagai pertanyaan seputar regulasi, panduan, dan informasi akademik tingkat Sarjana (S1) di lingkungan Universitas Sebelas Maret. 

Alih-alih mengandalkan pengetahuan umum dari internet, seluruh informasi dan jawaban yang diberikan oleh chatbot ditarik secara dinamis dari himpunan dokumen resmi universitas berformat PDF (baik dokumen digital maupun hasil *scan* yang diproses dengan *Optical Character Recognition*) yang tersimpan dalam basis data internal sistem.

---

## 🚀 Teknologi yang Digunakan

Proyek ini dibangun secara *end-to-end* menggunakan teknologi modern:
- **Backend & API:** [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Large Language Model:** [Google Gemini 2.5 Flash](https://aistudio.google.com/) (via API)
- **Embedding Model:** Gemini Embedding (untuk semantik *vector*)
- **Vector Database:** [ChromaDB](https://www.trychroma.com/) (Penyimpanan vektor lokal persisten)
- **OCR Engine:** [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) dipadukan dengan [OpenCV](https://opencv.org/) (Computer Vision)
- **Frontend:** Vanilla HTML, CSS, JavaScript (Terintegrasi dengan Markdown parser)

---

## ⚙️ Cara Menjalankan Sistem (*Local Setup*)

### 1. Persyaratan Sistem
- Python 3.10 atau lebih baru
- Tesseract OCR terinstal di sistem operasi Anda (tambahkan ke PATH)
- Akun Google AI Studio untuk mendapatkan API Key Gemini

### 2. Instalasi Dependensi
Lakukan *clone* repositori ini, lalu jalankan instalasi *virtual environment* dan paket yang dibutuhkan:

```bash
# Membuat virtual environment (opsional namun disarankan)
python -m venv .venv

# Aktivasi virtual environment (Mac/Linux)
source .venv/bin/activate
# Aktivasi virtual environment (Windows)
.venv\Scripts\activate

# Install dependensi
pip install -r requirements.txt
```

### 3. Konfigurasi Lingkungan (.env)
Buat sebuah file bernama `.env` di direktori utama (root), lalu masukkan API Key Anda:
```env
GEMINI_API_KEY=AIzaSy... (API Key Anda)
```
Seluruh konfigurasi parameter RAG, seperti *top_k*, *min_score* (threshold), dan parameter OCR disimpan dalam file `config.yaml`.

### 4. Ekstraksi Dokumen (Ingestion / Offline Phase)
Sebelum chatbot dapat menjawab, Anda harus memasukkan dokumen-dokumen akademik ke dalam sistem. Taruh file PDF di dalam folder `data/uploads/`, lalu jalankan skrip berikut untuk memulai proses OCR, *chunking*, *embedding*, dan injeksi ke ChromaDB:

```bash
python scripts/seed_database.py
```
*(Proses ini mungkin memakan waktu tergantung jumlah dokumen dan performa Tesseract OCR).*

### 5. Menjalankan Server Web (Online Phase)
Setelah *database vector* terisi, jalankan server *backend* FastAPI:

```bash
uvicorn app:app --reload
```
Akses antarmuka web melalui browser Anda pada alamat: **http://127.0.0.1:8000**
