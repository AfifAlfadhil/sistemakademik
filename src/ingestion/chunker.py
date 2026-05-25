"""
chunker.py — Markdown Header Chunker untuk Dokumen Hukum JDIH UNS

Modul ini bertanggung jawab untuk memecah teks Markdown hasil dari parser.py
menjadi chunks (potongan) berdasarkan level header Markdown (# BAB, ## Pasal).
Satu chunk idealnya merepresentasikan satu Pasal utuh untuk menjaga konteks semantik.
"""

import re
import uuid

def chunk_markdown(markdown_text: str, doc_metadata: dict, max_size: int = 1500, overlap: int = 200) -> list[dict]:
    """
    Memecah teks Markdown menjadi chunk berdasarkan header (# BAB, ## Pasal).
    
    Args:
        markdown_text: Teks dokumen utuh berformat Markdown
        doc_metadata: Metadata dokumen asal (dari parser)
        max_size: Ukuran maksimal karakter per chunk (jika satu pasal terlalu panjang)
        overlap: Jumlah karakter overlap untuk chunk yang terpaksa dipotong karena max_size
        
    Returns:
        List of dict, berisi chunk dan metadatanya.
    """
    lines = markdown_text.split('\n')
    chunks = []
    
    current_bab = None
    current_pasal = None
    current_bagian = None
    
    current_chunk_text = []
    
    def finalize_chunk():
        if current_chunk_text:
            text = '\n'.join(current_chunk_text).strip()
            if text:
                # Jika ukuran teks terlalu panjang dari max_size, kita lakukan secondary split
                if len(text) > max_size:
                    _split_large_chunk_and_append(text)
                else:
                    _append_chunk(text)
            current_chunk_text.clear()

    def _append_chunk(text: str):
        # Buat ID unik
        source_name = doc_metadata.get("source_file", "unknown").replace(".pdf", "")
        # bersihkan nama agar aman untuk ID
        source_name = re.sub(r'[^a-zA-Z0-9]', '_', source_name).strip('_')[:20]
        chunk_id = f"{source_name}_chunk_{str(uuid.uuid4())[:8]}"
        
        chunks.append({
            "id": chunk_id,
            "text": text,
            "source_file": doc_metadata.get("source_file", ""),
            "metadata": {
                "bab": current_bab,
                "pasal": current_pasal,
                "bagian": current_bagian,
                "chunk_length": len(text)
            }
        })

    def _split_large_chunk_and_append(text: str):
        """Memotong teks yang terlalu panjang menjadi beberapa chunk dengan overlap."""
        # Coba split by empty lines (paragraphs)
        paragraphs = text.split('\n\n')
        
        # Jika tidak ada empty lines, fallback ke single newline
        if len(paragraphs) == 1:
            paragraphs = text.split('\n')
            
        current_sub_chunk = []
        current_len = 0
        
        for p in paragraphs:
            # Jika satu paragraf/baris itu sendiri sudah melebihi max_size
            if len(p) > max_size:
                # Terpaksa split paksa berdasarkan karakter (dengan overlap)
                if current_sub_chunk:
                    _append_chunk('\n'.join(current_sub_chunk))
                    current_sub_chunk = []
                    current_len = 0
                
                # Potong paragraf besar ini per max_size karakter
                idx = 0
                while idx < len(p):
                    end_idx = min(idx + max_size, len(p))
                    _append_chunk(p[idx:end_idx])
                    idx += max_size - overlap
                continue
                
            if current_len + len(p) > max_size and current_sub_chunk:
                joined_text = '\n'.join(current_sub_chunk)
                _append_chunk(joined_text)
                
                # Keep overlap (last paragraph or last overlap chars)
                overlap_text = joined_text[-overlap:]
                # Try to find a clean word boundary
                space_idx = overlap_text.find(' ')
                if space_idx > 0:
                    overlap_text = overlap_text[space_idx+1:]
                
                current_sub_chunk = [overlap_text, p]
                current_len = len(overlap_text) + 1 + len(p)
            else:
                current_sub_chunk.append(p)
                current_len += len(p) + 1
                
        if current_sub_chunk:
            _append_chunk('\n'.join(current_sub_chunk))


    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith("# BAB "):
            finalize_chunk()
            current_bab = stripped.replace("# BAB ", "BAB ")
            current_pasal = None  # Reset pasal saat pindah BAB
            current_chunk_text.append(line)
            
        elif stripped.startswith("## Pasal "):
            finalize_chunk()
            pasal_match = re.search(r'Pasal\s+(\d+)', stripped)
            if pasal_match:
                current_pasal = pasal_match.group(1)
            current_chunk_text.append(line)
            
        elif stripped.startswith("### Bagian "):
            finalize_chunk()
            bagian_match = re.search(r'Bagian\s+(\w+)', stripped)
            if bagian_match:
                current_bagian = bagian_match.group(1)
            current_chunk_text.append(line)
            
        elif stripped.startswith("# ") and "BAB" not in stripped:
            # Header Markdown umum (misal untuk dokumen non-hukum)
            finalize_chunk()
            current_chunk_text.append(line)
            
        elif stripped.startswith("## ") and "Pasal" not in stripped:
            # Header Markdown Level 2 umum
            finalize_chunk()
            current_chunk_text.append(line)
            
        else:
            current_chunk_text.append(line)
            
    # Flush sisa terakhir
    finalize_chunk()
    
    return chunks
