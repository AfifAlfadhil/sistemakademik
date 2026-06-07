# Dokumentasi Proyek Sistem Akademik (RAG)

## Gambaran Umum Proyek
Proyek ini adalah sistem **Retrieval-Augmented Generation (RAG)** cerdas yang bertugas mencerna dokumen kompleks berskala besar (seperti SK Rektor, Pedoman, Kalender Akademik), memahaminya, dan kemudian menjadi sistem asisten pintar (*AI Assistant*) yang siap melayani pertanyaan berbasis fakta dari dokumen tersebut.

Sistem dirancang dengan arsitektur yang sangat modular (*Separation of Concerns*). Pemrosesan data mentah (*Back-office*) dan eksekusi aplikasi antarmuka dibuat terpisah secara arsitektur namun tetap berkesinambungan.

---

## Arsitektur dan Pipeline Saat Ini (Penyediaan Data)
Saat ini, proyek telah merampungkan fondasi utama yaitu **Penyediaan Data** (*Data Provisioning*). Pipeline ini memastikan dokumen PDF mentah dikonversi menjadi representasi matematis yang cerdas. Proses ini diorkestrasi oleh dua *runner scripts* utama di folder `dev/` yang memanggil logika inti dari folder `src/`.

Berikut adalah alur lengkap (*End-to-End*) dari *pipeline* yang sudah beroperasi saat ini:

### 1. Ekstraksi Dokumen Mentah (PDF Extractor & OCR)
Proses dimulai ketika skrip `dev/run_ingestion.py` membaca file PDF dari `dev/data/raw/`. Modul yang menangani ini berada di `src/ingestion/pdf_extractor.py` dan `src/ingestion/image_preprocessing.py`.
- **Ekstraksi Teks Asli**: Menggunakan pustaka **PyMuPDF** (`fitz`) untuk menarik teks digital bawaan secara cepat.
- **Computer Vision & OCR**: Untuk gambar grafik, hasil *scan*, atau tabel yang rumit, modul mengandalkan **OpenCV** (untuk pembersihan gambar tingkat piksel seperti *bilateral filtering* dan koreksi kemiringan/deskew) yang kemudian dipindai oleh **Tesseract OCR** (`pytesseract`).
- **Konfigurasi Fleksibel**: Parameter ekstraksi seperti resolusi pembacaan (`dpi: 300`) hingga mode segmentasi Tesseract (`psm_text`, `psm_table`) secara dinamis ditarik dari file terpusat `config.yaml`.

### 2. Pembersihan Teks (Cleaning)
Setelah seluruh teks mentah berhasil ditarik, teks tersebut diteruskan ke modul `src/ingestion/cleaning.py`.
- Teks diproses menggunakan *Regular Expression* (RegEx) untuk menghapus karakter sampah, menormalisasi spasi ekstra, menyambungkan pemutusan kata antar-halaman (*hyphenation*), dan membuang elemen *header/footer* yang tidak membawa makna semantik.

### 3. Pemotongan Teks (Semantic Chunking)
Teks yang sudah bersih dan amat panjang kemudian dikirim ke modul `src/ingestion/chunking.py`.
- Sistem menggunakan `langchain-text-splitters` untuk memecah teks ke dalam *chunks* (paragraf/blok kalimat) sebesar **1000 karakter** dengan **150 karakter overlap** (irisan). Overlap ini krusial agar konteks kalimat yang terpotong di batas chunk tidak hilang.
- **Output**: Hasil chunk ini disimpan sebagai file `.md` (untuk dicek manual) dan `.json` (untuk tahap selanjutnya) di dalam direktori `dev/data/processed/`.

### 4. Konversi Vektor (Embedding Service)
Tahap kedua diorkestrasi oleh `dev/run_vector_store.py`. Skrip ini membaca file `.json` hasil *chunking* dan memanggil modul `src/embedding/service.py`.
- **Google Gemini API**: Modul ini terhubung langsung ke layanan Google via pustaka `google-genai` (autentikasi otomatis menggunakan `GEMINI_API_KEY` di file `.env`).
- Setiap *chunk* teks ditransformasikan menjadi deretan vektor matematika berdimensi tinggi (**3072 dimensi**) menggunakan model *State-of-the-Art* `gemini-embedding-2`. Sistem memproses hal ini dalam bentuk *batch* secara simultan agar lebih cepat.

### 5. Penyimpanan Vektor (Vector Storage)
Terakhir, modul `src/storage/vector_store.py` akan diinisialisasi.
- Seluruh *chunks* teks beserta angka vektor dan metadatanya disuntikkan ke dalam basis data **Chroma DB**.
- **Output Produksi**: Sebuah basis data terstruktur tercipta di direktori *root* (`./chroma_db`). Database ini sewaktu-waktu siap di-*query* (dicari) kecepatannya.
- **Output Evaluasi**: Skrip secara otomatis juga mencetak sampel dari database ke dalam `dev/data/eval/vector_store_sample.md` untuk memudahkan pengguna memantau atau melaporkan hasil kerja mesin secara visual.

---

## Struktur Direktori
```text
.
├── .env                # Variabel lingkungan (API Key)
├── config.yaml         # Hyperparameter pemrosesan (Blueprint Sistem)
├── requirements.txt    # Ketergantungan pustaka Python
├── chroma_db/          # [Generated] Basis data vektor produksi
├── dev/                # Alat Monitoring, Development, dan Runner
│   ├── data/           # [Generated] Tempat berkumpulnya file raw, processed, dan eval
│   ├── run_ingestion.py
│   └── run_vector_store.py
└── src/                # Kode sumber utama (Logika Inti Terisolasi)
    ├── embedding/      # Layanan konversi teks ke vektor (Google Gemini)
    ├── ingestion/      # Modul Parser, Computer Vision, OCR, dan Chunking
    └── storage/        # Modul jembatan komunikasi ke database (Chroma DB)
```

---

## Rencana Pengembangan Selanjutnya (Roadmap 🚀)
Setelah basis pengetahuan (Vektor) terbentuk secara solid di atas, fase berikutnya berfokus pada pembangunan **Mesin Pencari & Asisten AI** yang melayani pengguna akhir. 

Seluruh **konfigurasi hyperparameter dan arsitektur library yang dibutuhkan untuk merajut fase ini sebenarnya sudah dirancang sedari awal** dan di-*comment out* di dalam file `config.yaml` dan `requirements.txt`. Kita hanya tinggal membuka tanda komentarnya dan mulai mengimplementasikan fondasi berikut:

### 1. Sistem Retrieval Hibrida (`src/retrieval/`)
Membangun algoritma pencarian mutakhir. Daripada sekadar mencocokkan kemiripan vektor (*Semantic Search*), sistem akan digabungkan dengan **BM25 Keyword Search** (Pencarian leksikal spesifik). Hasil dari keduanya akan digabungkan lewat metode **Reciprocal Rank Fusion (RRF)**. Konfigurasi jumlah pencarian (`retrieval: top_k: 5`) sudah disiapkan di `config.yaml`.

### 2. Generasi Jawaban LLM (`src/llm/`)
Membangun modul generasi sintesis (*Generative Module*) yang bertugas "membaca" konteks dari hasil *Retrieval* dan merumuskan jawaban yang sangat alami menggunakan **Google Gemini 2.5 Flash**. 
- Parameter `model: "gemini-2.5-flash"`, `temperature: 0.2` (untuk menekan halusinasi akademis), dan `max_tokens: 2048` sudah diatur matang sebagai *blueprint* di dalam `config.yaml`.

### 3. Manajemen Database Percakapan (`src/database/`)
Agar AI mengingat riwayat percakapan pengguna sebelumnya (berkemampuan *Follow-up Questions*), kita akan menanamkan *database* asinkron ringan (**SQLite** via modul `aiosqlite`). 
- Parameter panjang memori obrolan (`history_window: 6`) sudah diplot di `config.yaml`, dan *library* `aiosqlite` sudah tercantum di *roadmap* `requirements.txt`.

### 4. REST API Backend & Server (`app.py`)
Membangun gerbang utama (*Backend Server*) berskala *Production* agar otak AI ini bisa dikomunikasikan ke *web frontend*, UI interaktif, maupun *mobile app*.
- **Teknologi Utama**: Menggunakan **FastAPI** dengan web-server **Uvicorn**, sanggup memproses *file upload* lewat `python-multipart`, dan menangani file I/O secara kilat dengan `aiofiles`. Semua spesifikasinya sengaja sudah direkam di `requirements.txt`.
- **Fitur API**: Membangun *endpoint* khusus seperti `/chat` (untuk respons *streaming* secara instan ke layar pengguna bak ChatGPT), dan `/upload` (untuk menelan SK PDF baru dari pengguna tanpa harus lewat terminal).
