import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.llm.chatbot import AcademicChatbot

chatbot = AcademicChatbot()

while True:
    query = input("\nPertanyaan: ").strip()

    if query.lower() == "exit":
        break

    answer = chatbot.ask(query)

    print("\n" + "=" * 80)
    print(answer)
    print("=" * 80)