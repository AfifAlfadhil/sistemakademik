"""
parser.py — PDF Parser & Cleaner untuk Dokumen Hukum JDIH UNS

Modul ini bertanggung jawab untuk:
1. Membaca file PDF menggunakan PyMuPDF (fitz)
2. Mendeteksi dan mengekstrak tabel asli sebagai format Markdown (mengabaikan layout tabel palsu)
3. Mengekstrak teks blok demi blok dan menggabungkan kalimat yang terputus dengan cerdas
4. Menambahkan header Markdown (# BAB, ## Pasal)
5. Menghasilkan output Markdown lengkap per dokumen
6. Mengekstrak metadata dokumen
"""

import fitz
import re
import pandas as pd
import pytesseract
from PIL import Image
from pathlib import Path

def _clean_text_block(text: str) -> str:
    """Bersihkan dan format sebuah blok teks menjadi Markdown."""
    # Bersihkan artefak
    text = text.replace('\xa0', ' ')
    text = re.sub(r'^\s*SALINAN\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*ttd\.?\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'^\s*PERATURAN REKTOR UNIVERSITAS SEBELAS MARET\s*$', '', text, flags=re.MULTILINE)
    
    lines_raw = text.split('\n\n')
    joined = []
    current = ""
    
    for block in lines_raw:
        # Pisahkan list item yang tergabung sebaris akibat OCR
        block = re.sub(r'([^\n])\s+([a-z]\.\s+[A-Z])', r'\1\n\2', block)
        
        # Pisahkan preamble (Menimbang, Mengingat, Memutuskan, Menetapkan) menjadi baris terpisah
        block = re.sub(r'^(MENIMBANG|MENGINGAT|MEMUTUSKAN|MENETAPKAN)\s*:\s+(?=\S)', r'\1 :\n', block, flags=re.IGNORECASE | re.MULTILINE)
        
        lines = block.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue
            
            # Format bullet points to Markdown standard
            line = re.sub(r'^[-●*+]\s*(\u200b\s*)?', '- ', line)
            
            is_list = re.match(r'^(\d+\.|[a-z]\.|\([a-z0-9]+\)|-)(\s|$)', line, re.IGNORECASE)
            
            # Deteksi Hirarki Header Legal Ekstrem (Sangat spesifik agar tidak false positive)
            upper_line = line.upper()
            is_header = False
            heading_level = ""
            
            # Hanya match jika line benar-benar format heading legal struktural
            if re.match(r'^BAB\s+[IVXLCDM]+', upper_line):
                is_header, heading_level = True, "#"
            elif re.match(r'^BAGIAN\s+(KESATU|KEDUA|KETIGA|KEEMPAT|KELIMA|KEENAM|KETUJUH|KEDELAPAN|KESEMBILAN|KESEPULUH)', upper_line):
                is_header, heading_level = True, "##"
            elif re.match(r'^PARAGRAF\s+\d+', upper_line):
                is_header, heading_level = True, "###"
            elif re.match(r'^PASAL\s+\d+', upper_line):
                is_header, heading_level = True, "####"
            elif re.match(r'^(MENIMBANG|MENGINGAT|MEMUTUSKAN|MENETAPKAN)\s*[:]?$', upper_line):
                if line.isupper() or ":" in line:
                    is_header, heading_level = True, "##"
                
            if is_header:
                line = re.sub(r'^[-●*+]\s*', '', line)
                line = f"{heading_level} {line}"
            
            # Jika ini list, header, atau kalimat sebelumnya berakhir dengan terminator DAN diikuti huruf kapital
            prev_terminator = (current.endswith(('.', ':', ';', '!', '?')) and line[0].isupper()) if current else False
            prev_is_header = current.startswith(('# ', '## ', '### ', '#### ')) if current else False
            
            is_new_block = (i == 0)
            is_continuation_of_block = False
            if is_new_block and current:
                # Kita gabung beda block JIKA block sblmnya tidak diakhiri terminator, 
                # DAN (cukup panjang ATAU baris baru diawali huruf kecil)
                if not current.endswith(('.', ':', ';', '!', '?')) and (len(current) > 40 or line[0].islower()):
                    is_continuation_of_block = True
                    
            force_split_block = (is_new_block and current and not is_continuation_of_block)
            
            if is_list or is_header or prev_terminator or prev_is_header or force_split_block:
                if current: joined.append(current)
                current = line
            else:
                if current:
                    if current.endswith('-'): current = current[:-1] + line
                    else: current = current + " " + line
                else:
                    current = line
                    
    if current: joined.append(current)
            
    return "\n\n".join(joined)

def parse_legal_pdf_to_markdown(pdf_path: str) -> str:
    """
    Ekstrak PDF ke dalam format Markdown.
    Menggunakan deteksi tabel pintar untuk mengubah tabel asli menjadi Markdown Table,
    dan mengabaikan layout dokumen yang salah dideteksi sebagai tabel.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File PDF tidak ditemukan: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    all_elements = []
    
    for page_num, page in enumerate(doc):
        # 1. Temukan tabel valid
        tabs = page.find_tables()
        valid_tables = []
        if tabs.tables:
            for tab in tabs:
                df = tab.to_pandas()
                # Hitung empty ratio untuk membedakan tabel asli dan fake layout
                total_cells = df.size + len(df.columns)
                empty_cells = sum(1 for c in df.columns if "Col" in str(c) or str(c).strip() == "")
                for col in df.columns:
                    for val in df[col]:
                        if pd.isna(val) or str(val).strip() == "":
                            empty_cells += 1
                            
                empty_ratio = empty_cells / total_cells if total_cells > 0 else 0
                
                # Jika sel kosong <= 40%, itu adalah tabel asli
                if empty_ratio <= 0.4:
                    valid_tables.append({
                        'bbox': tab.bbox,
                        'df': df
                    })
        
        # 2. Ambil semua teks blocks
        blocks = page.get_text("blocks")
        text_blocks = [b for b in blocks if b[6] == 0]
        
        # 3. Filter text_blocks yang tidak overlap dengan tabel valid
        filtered_text_blocks = []
        for b in text_blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            is_overlap = False
            for vt in valid_tables:
                tx0, ty0, tx1, ty1 = vt['bbox']
                if y0 >= ty0 - 5 and y1 <= ty1 + 5 and x0 >= tx0 - 5 and x1 <= tx1 + 5:
                    is_overlap = True
                    break
            if not is_overlap:
                filtered_text_blocks.append(b)
                
        # 4. Kumpulkan elemen-elemen halaman
        page_elements = []
        for vt in valid_tables:
            df = vt['df']
            
            def _clean_cell(x):
                if pd.isna(x): return ""
                # Ganti semua karakter whitespace (termasuk newline) berturut-turut menjadi satu spasi
                return re.sub(r'\s+', ' ', str(x)).strip()
                
            df.columns = [_clean_cell(c) for c in df.columns]
            df = df.map(_clean_cell)
            md_table = df.to_markdown(index=False)
            page_elements.append({
                'y0': vt['bbox'][1],
                'type': 'table',
                'raw': md_table
            })
            
        for b in filtered_text_blocks:
            page_elements.append({
                'y0': b[1],
                'type': 'text',
                'raw': b[4]
            })
            
        # Urutkan berdasarkan y0
        page_elements.sort(key=lambda e: e['y0'])
        
        # 4.5 Fallback OCR jika teks sangat sedikit (kemungkinan dokumen hasil scan)
        page_char_count = sum(len(e['raw']) for e in page_elements)
        if page_char_count < 50:
            # print(f"    [OCR] Halaman {page_num + 1} minim teks, menjalankan Tesseract OCR...")
            try:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = pytesseract.image_to_string(img, lang="ind", config="--psm 6")
                if ocr_text.strip():
                    # Timpa elemen halaman dengan hasil OCR
                    page_elements = [{
                        'y0': 0,
                        'type': 'text',
                        'raw': ocr_text
                    }]
            except Exception as e:
                print(f"    [OCR Error] Gagal menjalankan OCR pada halaman {page_num + 1}: {e}")
        
        # 5. Gabungkan text blocks yang berdekatan dan bersihkan
        current_text_buffer = []
        for e in page_elements:
            if e['type'] == 'table':
                if current_text_buffer:
                    merged = "\n\n".join(current_text_buffer)
                    all_elements.append(_clean_text_block(merged))
                    current_text_buffer = []
                all_elements.append(e['raw'] + "\n")
            else:
                current_text_buffer.append(e['raw'])
                
        # Flush sisa
        if current_text_buffer:
            merged = "\n\n".join(current_text_buffer)
            cleaned = _clean_text_block(merged)
            if cleaned.strip():
                all_elements.append(cleaned)
                
    doc.close()
    
    # Gabungkan semua halaman
    final_md = "\n\n".join(all_elements)
    
    # Bersihkan multiple blank lines berlebihan
    final_md = re.sub(r'\n{3,}', '\n\n', final_md)
    return final_md

def extract_document_metadata(markdown_text: str, filename: str) -> dict:
    """
    Ekstrak metadata dokumen dari awal teks Markdown.
    """
    sample_text = markdown_text[:5000]
    
    doc_type = "Dokumen Hukum"
    if "PERATURAN REKTOR" in sample_text or "Peraturan Rektor" in sample_text:
        doc_type = "Peraturan Rektor"
    elif "KEPUTUSAN REKTOR" in sample_text or "Keputusan Rektor" in sample_text:
        doc_type = "Keputusan Rektor"
    elif "STATUTA" in sample_text or "Statuta" in sample_text:
        doc_type = "Statuta"

    doc_number = "N/A"
    number_match = re.search(r'NOMOR\s+(\d+)', sample_text, re.IGNORECASE)
    if number_match:
        doc_number = number_match.group(1)

    doc_year = "N/A"
    year_match = re.search(r'TAHUN\s+(\d{4})', sample_text, re.IGNORECASE)
    if year_match:
        doc_year = year_match.group(1)

    doc_topic = "N/A"
    if "TENTANG" in sample_text:
        topic_match = re.search(r'TENTANG\s*\n\s*([^DENGAN]+)', sample_text)
        if topic_match:
            doc_topic = topic_match.group(1).replace('\n', ' ').strip()
        else:
            topic_match = re.search(r'TENTANG\s+(.*?)(?=\n\n|\n[A-Z])', sample_text, re.DOTALL)
            if topic_match:
                doc_topic = topic_match.group(1).replace('\n', ' ').strip()

    doc_institution = "UNS"
    if "UNIVERSITAS SEBELAS MARET" in sample_text:
        doc_institution = "Universitas Sebelas Maret"

    effective_info = "Tidak terdeteksi"
    effective_match = re.search(r'(mulai berlaku pada tanggal.*?)\.', markdown_text[-2000:], re.IGNORECASE)
    if effective_match:
        effective_info = effective_match.group(1).replace('\n', ' ').strip()

    return {
        "doc_type": doc_type,
        "doc_number": doc_number,
        "doc_year": doc_year,
        "doc_topic": doc_topic,
        "doc_institution": doc_institution,
        "effective_info": effective_info,
        "source_file": filename,
        "total_characters": len(markdown_text)
    }
