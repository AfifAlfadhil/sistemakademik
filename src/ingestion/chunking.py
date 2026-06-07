"""
chunking.py — Text Splitting menggunakan RecursiveCharacterTextSplitter

Memecah teks panjang menjadi chunks yang optimal untuk embedding dan retrieval.
"""

import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(
    text: str,
    source_file: str,
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    separators: list[str] | None = None,
) -> list[dict]:
    """
    Pecah teks menjadi chunks menggunakan RecursiveCharacterTextSplitter.
    
    Args:
        text: Teks yang akan di-chunk
        source_file: Nama file sumber PDF
        document_id: UUID dokumen
        chunk_size: Ukuran maksimal chunk (karakter)
        chunk_overlap: Overlap antar chunk (karakter)
        separators: List separator untuk splitting
    
    Returns:
        List of chunk dicts dengan metadata
    """
    if not text or not text.strip():
        return []

    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        length_function=len,
        is_separator_regex=False,
    )

    text_chunks = splitter.split_text(text)

    chunks = []
    for i, content in enumerate(text_chunks):
        content = content.strip()
        if not content:
            continue

        chunk = {
            "chunk_id": str(uuid.uuid4()),
            "source_file": source_file,
            "document_id": document_id,
            "chunk_index": i,
            "content": content,
            "char_count": len(content),
        }
        chunks.append(chunk)

    return chunks
