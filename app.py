"""
app.py — FastAPI Backend for Academic RAG System
"""
import os
import sys
import uuid
import json
import time
import hashlib
import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import aiosqlite

# Tambahkan root directory project ke sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.llm.chatbot import AcademicChatbot
from src.config import config

app = FastAPI(title="Sistem Akademik RAG API")

# Middleware untuk mematikan cache browser agar selalu mendapatkan data terbaru otomatis
@app.middleware("http")
async def add_cache_control_header(request, call_next):
    response = await call_next(request)
    # Jangan cache response untuk API
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Initialize Chatbot
chatbot = AcademicChatbot()

DB_PATH = PROJECT_ROOT / "data" / "db" / "chat_history.db"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@app.on_event("startup")
async def startup():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                sources TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT DEFAULT 'user'
            )
        ''')
        
        # Add username column to sessions table if it doesn't exist
        try:
            await db.execute("ALTER TABLE sessions ADD COLUMN username TEXT")
            await db.commit()
        except sqlite3.OperationalError:
            pass

        # Migrate existing messages' session_ids to sessions table if not present, using first message as title
        async with db.execute('''
            SELECT m.session_id, m.content 
            FROM messages m
            WHERE m.role = 'user' AND m.session_id NOT IN (SELECT session_id FROM sessions)
            GROUP BY m.session_id
            HAVING min(m.timestamp)
        ''') as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                if row[0]:
                    title = row[1][:30] + "..." if len(row[1]) > 30 else row[1]
                    await db.execute(
                        "INSERT OR IGNORE INTO sessions (session_id, username, title) VALUES (?, ?, ?)",
                        (row[0], "user", title)
                    )
        
        # Backfill existing sessions that have NULL username
        await db.execute("UPDATE sessions SET username = 'user' WHERE username IS NULL")
        
        # Update existing sessions that have title 'Sesi Riwayat' to their first message content
        async with db.execute('''
            SELECT m.session_id, m.content 
            FROM messages m
            INNER JOIN sessions s ON m.session_id = s.session_id
            WHERE s.title = 'Sesi Riwayat' AND m.role = 'user'
            GROUP BY m.session_id
            HAVING min(m.timestamp)
        ''') as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                title = row[1][:30] + "..." if len(row[1]) > 30 else row[1]
                await db.execute(
                    "UPDATE sessions SET title = ? WHERE session_id = ?",
                    (title, row[0])
                )

        # Seed default users if table is empty
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 0:
                await db.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    ("admin", hash_password("admin123"), "admin")
                )
                await db.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                    ("user", hash_password("user123"), "user")
                )
        await db.commit()

class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/api/register")
async def register(request: AuthRequest):
    username = request.username.strip()
    password = request.password
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username dan password tidak boleh kosong")
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username minimal 3 karakter")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
        
    hashed = hash_password(password)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed, "user"))
            await db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"message": "Registrasi berhasil"}

@app.post("/api/login")
async def login(request: AuthRequest):
    username = request.username.strip()
    password = request.password
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username dan password tidak boleh kosong")
        
    hashed = hash_password(password)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT username, role FROM users WHERE username = ? AND password = ?", (username, hashed))
        user = await cursor.fetchone()
        
    if not user:
        raise HTTPException(status_code=400, detail="Username atau password salah")
        
    return {
        "username": user["username"],
        "role": user["role"],
        "message": "Login berhasil"
    }

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class Source(BaseModel):
    title: str
    file: str

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[Source] | None = None

@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, x_user_username: str | None = Header(None)):
    if not request.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    session_id = request.session_id or str(uuid.uuid4())
    username = x_user_username or "guest"
    
    try:
        # Save user message and ensure session exists with username
        import sqlite3
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.cursor()
            cursor.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
            session_exists = cursor.fetchone()
            
            if not session_exists:
                title = request.message[:30] + "..." if len(request.message) > 30 else request.message
                db.execute(
                    "INSERT INTO sessions (session_id, username, title) VALUES (?, ?, ?)",
                    (session_id, username, title)
                )
                
            db.execute("INSERT INTO messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)", 
                             (session_id, "user", request.message, None))
            db.commit()

        # Fetch conversation history (excluding the current user message we just inserted)
        history = []
        with sqlite3.connect(DB_PATH) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute('''
                SELECT role, content FROM messages 
                WHERE session_id = ? AND id < (SELECT max(id) FROM messages WHERE session_id = ?)
                ORDER BY timestamp DESC LIMIT ?
            ''', (session_id, session_id, config.get("chat", {}).get("history_window", 6)))
            rows = cursor.fetchall()
            for row in reversed(rows):
                history.append({"role": row["role"], "content": row["content"]})

        # Generate answer with history context
        answer, contexts = chatbot.ask(request.message, history=history)
        
        # Format sources
        sources_list = []
        if contexts:
            # Deduplicate by source_file
            seen_files = set()
            for ctx in contexts:
                source_file = ctx.get("source_file")
                if source_file and source_file not in seen_files:
                    seen_files.add(source_file)
                    sources_list.append({"title": source_file.replace(".pdf", ""), "file": source_file})
        
        sources_json = json.dumps(sources_list) if sources_list else None

        # Save assistant message
        with sqlite3.connect(DB_PATH) as db:
            db.execute("INSERT INTO messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)", 
                             (session_id, "assistant", answer, sources_json))
            db.commit()

        return ChatResponse(answer=answer, session_id=session_id, sources=sources_list)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history(x_user_username: str | None = Header(None)):
    """Mengembalikan daftar semua session_id yang pernah ada untuk user saat ini."""
    username = x_user_username or "guest"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT m.session_id, min(m.timestamp) as ts, m.content, s.title as custom_title
            FROM messages m
            INNER JOIN sessions s ON m.session_id = s.session_id
            WHERE m.role = 'user' AND s.username = ?
            GROUP BY m.session_id
            ORDER BY ts DESC
        ''', (username,))
        rows = await cursor.fetchall()
        
        sessions = []
        for row in rows:
            if row["custom_title"]:
                title = row["custom_title"]
            else:
                content = row["content"]
                title = content[:30] + "..." if len(content) > 30 else content
            sessions.append({
                "session_id": row["session_id"],
                "title": title
            })
        return {"sessions": sessions}

class SessionTitleRequest(BaseModel):
    title: str

@app.put("/api/history/{session_id}")
async def update_session_title(session_id: str, request: SessionTitleRequest, x_user_username: str | None = Header(None)):
    """Mengubah judul riwayat chat."""
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
        
    username = x_user_username or "guest"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT username FROM sessions WHERE session_id = ?", (session_id,))
        session = await cursor.fetchone()
        
        if session and session["username"] != username:
            raise HTTPException(status_code=403, detail="Tidak memiliki akses ke sesi ini")
            
        await db.execute('''
            INSERT INTO sessions (session_id, username, title) 
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET title = excluded.title, updated_at = CURRENT_TIMESTAMP
        ''', (session_id, username, request.title.strip()))
        await db.commit()
    return {"message": "Title updated successfully"}

@app.delete("/api/history/{session_id}")
async def delete_session(session_id: str, x_user_username: str | None = Header(None)):
    """Menghapus riwayat chat."""
    username = x_user_username or "guest"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT username FROM sessions WHERE session_id = ?", (session_id,))
        session = await cursor.fetchone()
        
        if session and session["username"] != username:
            raise HTTPException(status_code=403, detail="Tidak memiliki akses ke sesi ini")
            
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()
    return {"message": "Session deleted successfully"}

@app.get("/api/history/{session_id}")
async def get_session_messages(session_id: str, x_user_username: str | None = Header(None)):
    """Mengembalikan riwayat chat untuk sesi tertentu."""
    username = x_user_username or "guest"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT username FROM sessions WHERE session_id = ?", (session_id,))
        session = await cursor.fetchone()
        
        if session and session["username"] != username:
            raise HTTPException(status_code=403, detail="Tidak memiliki akses ke sesi ini")
            
        cursor = await db.execute('''
            SELECT role, content, sources
            FROM messages
            WHERE session_id = ?
            ORDER BY timestamp ASC
        ''', (session_id,))
        rows = await cursor.fetchall()
        
        messages = []
        for row in rows:
            msg = {
                "role": row["role"],
                "content": row["content"]
            }
            if row["sources"]:
                try:
                    msg["sources"] = json.loads(row["sources"])
                except:
                    pass
            messages.append(msg)
            
        return {"session_id": session_id, "messages": messages}


@app.get("/api/documents")
def get_documents():
    """Mengembalikan daftar dokumen dari database (ChromaDB) dan folder uploads."""
    db_docs = chatbot.retriever.vector_store.get_all_documents()
    db_files = {doc["file"]: doc for doc in db_docs}
    
    uploads_dir = PROJECT_ROOT / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    all_documents = []
    for file_path in uploads_dir.glob("*.pdf"):
        filename = file_path.name
        mtime = file_path.stat().st_mtime
        date_str = time.strftime("%d %b %Y", time.localtime(mtime))
        
        if filename in db_files:
            doc = db_files[filename]
            doc["date"] = date_str
            doc["status"] = "Ready"
            all_documents.append(doc)
        else:
            all_documents.append({
                "title": filename.replace(".pdf", ""),
                "file": filename,
                "date": date_str,
                "status": "Proses"
            })
            
    return {"documents": all_documents}


from fastapi import UploadFile, File, BackgroundTasks

# Dictionary global untuk menampung real-time logs unggah dokumen
upload_logs = {}

def log_message(filename: str, message: str):
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    if filename not in upload_logs:
        upload_logs[filename] = []
    upload_logs[filename].append(log_line)
    print(log_line)

def process_uploaded_pdf_background(pdf_path: Path, filename: str):
    import uuid
    from src.ingestion.pdf_extractor import extract_pdf_full_ocr
    from src.ingestion.chunking import chunk_text
    from src.config import config
    
    log_message(filename, f"Memulai pemrosesan dokumen: {filename}")
    try:
        file_size = pdf_path.stat().st_size
        log_message(filename, f"Ukuran file PDF: {file_size} bytes")
        
        ocr_config = config.get("ocr", {})
        preprocessing_config = ocr_config.get("preprocessing", {})
        chunking_config = config.get("ingestion", {})
        embed_batch_size = config.get("embedding", {}).get("batch_size", 100)
        task_type_doc = config.get("embedding", {}).get("task_type_document", "RETRIEVAL_DOCUMENT")

        log_message(filename, "Menjalankan modul ekstraksi PDF OCR (Tesseract)...")
        extraction_result = extract_pdf_full_ocr(
            pdf_path=str(pdf_path),
            dpi=ocr_config.get("dpi", 300),
            tesseract_lang=ocr_config.get("tesseract_lang", "ind"),
            psm_text=ocr_config.get("tesseract_psm_text", 6),
            psm_table=ocr_config.get("tesseract_psm_table", 4),
            psm_mixed=ocr_config.get("tesseract_psm_mixed", 3),
            preprocessing_config=preprocessing_config,
        )
        raw_text = extraction_result.get("text", "")
        char_count = len(raw_text)
        log_message(filename, f"Ekstraksi teks selesai. Terbaca {char_count} karakter.")
        
        if char_count == 0:
            log_message(filename, "Peringatan: Tidak ada teks yang berhasil diekstrak.")

        log_message(filename, "Memecah teks menjadi chunk (chunk_size: 1000, overlap: 150)...")
        chunks = chunk_text(
            text=raw_text,
            source_file=filename,
            document_id=str(uuid.uuid4()),
            chunk_size=chunking_config.get("chunk_size", 1000),
            chunk_overlap=chunking_config.get("chunk_overlap", 150),
        )
        valid_chunks = [c for c in chunks if c.get("content", "").strip()]
        log_message(filename, f"Pemecahan teks selesai. Dihasilkan {len(valid_chunks)} chunk valid.")
        
        if not valid_chunks:
            log_message(filename, "ERROR: Tidak ada chunk teks valid yang ditemukan untuk di-embedding.")
            return
            
        texts = [c["content"] for c in valid_chunks]
        log_message(filename, "Membuat vektor embedding menggunakan Gemini API...")
        embeddings = chatbot.retriever.embedding_service.embed_texts(texts, batch_size=embed_batch_size, task_type=task_type_doc)
        log_message(filename, f"Sukses membuat {len(embeddings)} vektor embedding.")
        
        log_message(filename, "Menyimpan chunk dan embedding ke ChromaDB...")
        chatbot.retriever.vector_store.add_documents(valid_chunks, embeddings)
        log_message(filename, f"SUCCESS: Pemrosesan {filename} selesai dan siap dicari!")
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        log_message(filename, f"CRITICAL ERROR saat memproses dokumen: {e}")
        log_message(filename, error_trace)

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Mengunggah file PDF baru ke folder data/uploads dan mulai pemrosesan."""
    if not background_tasks:
        raise HTTPException(status_code=500, detail="Background tasks not available")
        
    uploads_dir = PROJECT_ROOT / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = uploads_dir / file.filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
        
    # Inisialisasi awal log untuk file ini
    import time as pytime
    timestamp = pytime.strftime("%Y-%m-%d %H:%M:%S")
    upload_logs[file.filename] = [
        f"[{timestamp}] Berhasil mengunggah berkas {file.filename} ke server.",
        f"[{timestamp}] Memulai background task untuk ekstraksi & embedding..."
    ]
        
    background_tasks.add_task(process_uploaded_pdf_background, file_path, file.filename)
        
    return {"message": "Berhasil mengunggah dokumen", "filename": file.filename}

@app.get("/api/upload/logs/{filename}")
def get_upload_logs(filename: str):
    """Mengembalikan log pemrosesan untuk file tertentu."""
    logs = upload_logs.get(filename, ["Menunggu pemrosesan dimulai..."])
    return {"filename": filename, "logs": logs}

# Mount static files for frontend
app.mount("/uploads", StaticFiles(directory=str(PROJECT_ROOT / "data" / "uploads")), name="uploads")
app.mount("/", StaticFiles(directory=str(PROJECT_ROOT / "app"), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
