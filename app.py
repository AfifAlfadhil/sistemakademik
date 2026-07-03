"""
app.py — FastAPI Backend for Academic RAG System
"""
import os
import sys
import uuid
import json
import time
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
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
        await db.commit()

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
def chat(request: ChatRequest):
    if not request.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        # Save user message
        import sqlite3
        with sqlite3.connect(DB_PATH) as db:
            db.execute("INSERT INTO messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)", 
                             (session_id, "user", request.message, None))
            db.commit()

        # Generate answer
        answer, contexts = chatbot.ask(request.message)
        
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
async def get_history():
    """Mengembalikan daftar semua session_id yang pernah ada (berdasarkan pesan pertama)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Ambil session_id, pesan pertama sebagai judul default, dan judul dari tabel sessions jika ada
        cursor = await db.execute('''
            SELECT m.session_id, min(m.timestamp) as ts, m.content, s.title as custom_title
            FROM messages m
            LEFT JOIN sessions s ON m.session_id = s.session_id
            WHERE m.role = 'user'
            GROUP BY m.session_id
            ORDER BY ts DESC
        ''')
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
async def update_session_title(session_id: str, request: SessionTitleRequest):
    """Mengubah judul riwayat chat."""
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
        
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO sessions (session_id, title) 
            VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET title = excluded.title, updated_at = CURRENT_TIMESTAMP
        ''', (session_id, request.title.strip()))
        await db.commit()
    return {"message": "Title updated successfully"}

@app.delete("/api/history/{session_id}")
async def delete_session(session_id: str):
    """Menghapus riwayat chat."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()
    return {"message": "Session deleted successfully"}

@app.get("/api/history/{session_id}")
async def get_session_messages(session_id: str):
    """Mengembalikan riwayat chat untuk sesi tertentu."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
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

def process_uploaded_pdf_background(pdf_path: Path, filename: str):
    import uuid
    from src.ingestion.pdf_extractor import extract_pdf_full_ocr
    from src.ingestion.chunking import chunk_text
    from src.config import config
    
    try:
        ocr_config = config.get("ocr", {})
        preprocessing_config = ocr_config.get("preprocessing", {})
        chunking_config = config.get("ingestion", {})
        embed_batch_size = config.get("embedding", {}).get("batch_size", 100)
        task_type_doc = config.get("embedding", {}).get("task_type_document", "RETRIEVAL_DOCUMENT")

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
        
        chunks = chunk_text(
            text=raw_text,
            source_file=filename,
            document_id=str(uuid.uuid4()),
            chunk_size=chunking_config.get("chunk_size", 1000),
            chunk_overlap=chunking_config.get("chunk_overlap", 150),
        )
        valid_chunks = [c for c in chunks if c.get("content", "").strip()]
        
        if not valid_chunks:
            return
            
        texts = [c["content"] for c in valid_chunks]
        embeddings = chatbot.retriever.embedding_service.embed_texts(texts, batch_size=embed_batch_size, task_type=task_type_doc)
        
        chatbot.retriever.vector_store.add_documents(valid_chunks, embeddings)
        print(f"Successfully processed and embedded {filename}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error processing {filename}: {e}")

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
        
    background_tasks.add_task(process_uploaded_pdf_background, file_path, file.filename)
        
    return {"message": "Berhasil mengunggah dokumen", "filename": file.filename}

# Mount static files for frontend
app.mount("/uploads", StaticFiles(directory=str(PROJECT_ROOT / "data" / "uploads")), name="uploads")
app.mount("/", StaticFiles(directory=str(PROJECT_ROOT / "app"), html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
