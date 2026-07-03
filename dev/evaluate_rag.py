import os
import sys
from pathlib import Path
import json
import time
import itertools

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.config import config
from src.retrieval.service import RetrievalService
from src.llm.chatbot import AcademicChatbot
from google import genai
import pytesseract
from PIL import Image
import fitz

# ==========================================
# 1. DATASET UJI
# ==========================================
TEST_CASES = [
    {
        "query": "Kapan batas akhir pembayaran UKT untuk semester ganjil?",
        "expected_keywords": ["14 juli", "25 juli", "pembayaran ukt"],
        "category": "Tabel/Jadwal"
    },
    {
        "query": "Bagaimana cara mengetahui PIN untuk melakukan Herregistrasi dan KRS?",
        "expected_keywords": ["melalui bank", "website siakad"], 
        "category": "Prosedur Umum"
    }
]

# ==========================================
# METRIK BANTUAN
# ==========================================
def calculate_ocr_metrics(text: str) -> dict:
    if not text:
        return {"char_count": 0, "word_count": 0, "line_count": 0, "noise_ratio": 0.0}
    
    char_count = len(text)
    word_count = len(text.split())
    line_count = len(text.split('\n'))
    
    valid_punctuation = set(".,;:()/-_?!'\"\n\t ")
    noise_chars = sum(1 for c in text if not c.isalnum() and c not in valid_punctuation)
    noise_ratio = (noise_chars / char_count) * 100 if char_count > 0 else 0.0
    
    return {
        "char_count": char_count,
        "word_count": word_count,
        "line_count": line_count,
        "noise_ratio": noise_ratio
    }

# ==========================================
# 2. EVALUASI OCR (KUANTITATIF)
# ==========================================
def evaluate_ocr(pdf_path, page_num=3):
    print("\n" + "="*60)
    print("🔬 EKSPERIMEN KUANTITATIF OCR: PSM 3 vs PSM 6")
    print("="*60)
    print("Evaluasi OCR termasuk kategori KUANTITATIF karena kita dapat mengukur metrik yang pasti:")
    print("Jumlah Karakter, Jumlah Kata, Jumlah Baris, dan Noise Ratio (%).\n")
    
    if not os.path.exists(pdf_path):
        print(f"⚠️ File uji OCR tidak ditemukan: {pdf_path}")
        return
        
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        img_path = "/tmp/test_ocr_page.png"
        pix.save(img_path)
        img = Image.open(img_path)
        
        text_psm3 = pytesseract.image_to_string(img, lang="ind", config="--psm 3")
        text_psm6 = pytesseract.image_to_string(img, lang="ind", config="--psm 6")
        
        m3 = calculate_ocr_metrics(text_psm3)
        m6 = calculate_ocr_metrics(text_psm6)
        
        print(f"📄 PSM 3 (Auto Page Segmentation):")
        print(f"   - Char Count : {m3['char_count']}")
        print(f"   - Word Count : {m3['word_count']}")
        print(f"   - Line Count : {m3['line_count']}")
        print(f"   - Noise Ratio: {m3['noise_ratio']:.2f}%\n")
        
        print(f"📄 PSM 6 (Uniform Block of Text):")
        print(f"   - Char Count : {m6['char_count']}")
        print(f"   - Word Count : {m6['word_count']}")
        print(f"   - Line Count : {m6['line_count']}")
        print(f"   - Noise Ratio: {m6['noise_ratio']:.2f}%\n")
        
        print("💡 Kesimpulan OCR:")
        print("Noise ratio yang lebih rendah dan jumlah kata/baris yang proporsional menunjukkan hasil ekstraksi tabel yang lebih akurat dan terstruktur.")
        
    except Exception as e:
        print(f"Gagal evaluasi OCR: {e}")

# ==========================================
# 3. EVALUASI KUANTITATIF (DOE RETRIEVAL)
# ==========================================
def evaluate_retrieval_doe():
    print("\n" + "="*60)
    print("📊 EKSPERIMEN KUANTITATIF (DOE): RETRIEVAL")
    print("="*60)
    
    retriever = RetrievalService()
    
    # DOE Parameters
    top_k_options = [5, 10, 15]
    min_score_options = [0.3, 0.5]
    
    print(f"{'Top K':<10} | {'Min Score':<12} | {'Recall':<10} | {'MRR':<10}")
    print("-" * 50)
    
    best_config = None
    best_mrr = -1
    
    for k, score in itertools.product(top_k_options, min_score_options):
        hits = 0
        mrr = 0.0
        
        for case in TEST_CASES:
            query = case["query"]
            expected = case["expected_keywords"]
            
            chunks = retriever.retrieve(query=query, top_k=k, min_score=score)
            
            rank = 0
            for i, chunk in enumerate(chunks):
                if any(kw.lower() in chunk["content"].lower() for kw in expected):
                    rank = i + 1
                    break
            
            if rank > 0:
                hits += 1
                mrr += 1.0 / rank
                
        recall_pct = (hits / len(TEST_CASES)) * 100
        avg_mrr = mrr / len(TEST_CASES)
        
        print(f"{k:<10} | {score:<12.2f} | {recall_pct:>6.1f}%   | {avg_mrr:.3f}")
        
        if avg_mrr > best_mrr:
            best_mrr = avg_mrr
            best_config = (k, score)
            
    print("-" * 50)
    if best_config:
        print(f"💡 Rekomendasi Retrieval: top_k={best_config[0]}, min_score={best_config[1]}")

# ==========================================
# 4. EVALUASI KUALITATIF (DOE GENERATION / LLM)
# ==========================================
def evaluate_generation_doe():
    print("\n" + "="*60)
    print("🤖 EKSPERIMEN KUALITATIF (DOE): LLM GENERATION")
    print("="*60)
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    judge_model = "gemini-2.5-flash"
    
    # DOE Parameters for LLM Generation
    temperatures = [0.1, 0.8]
    models = ["gemini-2.5-flash"]
    
    for model, temp in itertools.product(models, temperatures):
        print(f"\n>>> Menguji Parameter LLM: Model = {model}, Temperature = {temp}")
        print("-" * 50)
        
        # Override config secara dinamis
        if "llm" not in config:
            config["llm"] = {}
        config["llm"]["temperature"] = temp
        config["llm"]["model"] = model
        
        chatbot = AcademicChatbot()
        
        total_metrics = {"relevansi": 0, "factuality": 0, "completeness": 0}
        valid_cases = 0
        
        for idx, case in enumerate(TEST_CASES):
            query = case["query"]
            print(f"Q: {query}")
            
            answer, contexts = chatbot.ask(query)
            context_text = "\n".join([c["content"] for c in contexts])
            print(f"A: {answer[:100]}...\n")
            
            if "Rate Limit API" in answer:
                print("⚠️ Rate Limit tercapai, skip evaluasi LLM-Judge.")
                time.sleep(5)
                continue
                
            judge_prompt = f"""
            Kamu adalah juri independen penilai RAG.
            Nilai skala 1-5 untuk jawaban ini:
            
            PERTANYAAN: {query}
            KONTEKS: {context_text}
            JAWABAN: {answer}
            
            Metrik:
            1. Relevansi: Menjawab pertanyaan langsung tanpa bertele-tele.
            2. Factuality: HANYA berdasarkan konteks, tidak halusinasi.
            3. Completeness: Mencakup seluruh aspek penting di konteks.
            
            Output JSON:
            {{
                "relevansi": {{ "skor": 5, "alasan": "string" }},
                "factuality": {{ "skor": 5, "alasan": "string" }},
                "completeness": {{ "skor": 5, "alasan": "string" }}
            }}
            """
            
            try:
                response = client.models.generate_content(
                    model=judge_model,
                    contents=judge_prompt,
                    config=genai.types.GenerateContentConfig(response_mime_type="application/json")
                )
                result = json.loads(response.text)
                
                for key in ["relevansi", "factuality", "completeness"]:
                    skor = int(result.get(key, {}).get("skor", 0))
                    alasan = result.get(key, {}).get("alasan", "")
                    total_metrics[key] += skor
                    print(f" - {key.capitalize():<12}: {skor}/5 -> {alasan}")
                
                valid_cases += 1
                
            except Exception as e:
                print(f"Gagal evaluasi LLM-Judge: {e}")
                
            time.sleep(5) # Delay anti rate-limit
            
        if valid_cases > 0:
            print(f"\n📊 Rekap Rata-rata Skor Kualitatif (Temp {temp}):")
            for k, v in total_metrics.items():
                print(f" - {k.capitalize():<12}: {v/valid_cases:.1f} / 5.0")
        else:
            print("Tidak ada hasil valid.")

if __name__ == "__main__":
    sample_pdf = os.path.join(PROJECT_ROOT, "data", "uploads", "SK Rektor UNS Kalender AkademikTA 2026 2027.pdf")
    
    evaluate_ocr(sample_pdf, page_num=3)
    evaluate_retrieval_doe()
    evaluate_generation_doe()
    print("\n✅ SELESAI.")
