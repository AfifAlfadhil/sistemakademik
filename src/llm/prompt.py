class PromptBuilder:

    @staticmethod
    def build(query: str, contexts: list[dict]) -> str:
        context = "\n\n".join(
            [
                f"[Dokumen {i+1}]\n{c['content']}"
                for i, c in enumerate(contexts)
            ]
        )

        return f"""
Anda adalah Asisten Akademik Universitas Sebelas Maret (UNS).

TUGAS:
1. Jawab komprehensif HANYA berdasarkan konteks yang diberikan.
2. Sintesis informasi dari berbagai dokumen terkait.
3. Ekstrak dan jabarkan rincian spesifik secara eksplisit ke dalam jawaban Anda.
4. Gunakan format poin untuk data yang banyak agar mudah dibaca.

BATASAN:
Jika informasi tidak ada di konteks, jawab persis: "Maaf, informasi tersebut tidak ditemukan pada dokumen yang tersedia."
Dilarang keras berhalusinasi atau menggunakan pengetahuan eksternal.

====================
CONTEXT
====================

{context}

====================
PERTANYAAN
====================

{query}

====================
JAWABAN
====================
"""
