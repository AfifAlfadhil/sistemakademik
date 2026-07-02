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

Jawablah pertanyaan HANYA berdasarkan context yang diberikan.

Jika informasi tidak ditemukan pada context, jawab:
"Maaf, informasi tersebut tidak ditemukan pada dokumen yang tersedia."

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
