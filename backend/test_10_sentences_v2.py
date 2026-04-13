
import asyncio
import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

# Load .env from backend folder
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

async def test_10_sentences_v2():
    api_key = os.getenv("HINDSIGHT_API_KEY")
    base_url = os.getenv("HINDSIGHT_BASE_URL") or "https://api.hindsight.vectorize.io"
    
    client = Hindsight(api_key=api_key, base_url=base_url)
    bank_id = "udit"
    
    sentences = [
        "The student opened the Physics textbook at 9 AM.",
        "They started reading about Quantum Mechanics.",
        "At 10 AM, they made notes on wave-particle duality.",
        "They felt confused about the Heisenberg Uncertainty Principle.",
        "Around 11 AM, they took a short break to eat an apple.",
        "They resumed study by watching a YouTube video on Schrodinger's Cat.",
        "By noon, they had completed 5 practice problems.",
        "They discussed the concepts with a friend named Alex on Discord.",
        "They decided to focus on Entanglement in the afternoon session.",
        "Finally, they closed the book feeling much more confident."
    ]
    
    print("--- Ingesting 10 Study Session Sentences ---")
    for idx, sentence in enumerate(sentences):
        try:
            res = await client.aretain(
                bank_id=bank_id,
                content=sentence,
                metadata={"source": "study_session_test", "order": str(idx)}
            )
            print(f"Retained {idx + 1}: {sentence[:40]}...")
        except Exception as e:
            print(f"Failed to retain {idx + 1}: {e}")
            
    print("\n--- Reflecting on the Study Session ---")
    try:
        response = await client.areflect(
            bank_id=bank_id,
            query="Summarize the student's study progress and what they learned today.",
            context="Provide a chronological summary of the study session."
        )
        answer = getattr(response, 'text', getattr(response, 'answer', "No answer found"))
        print(f"\nAI Reflection Result:\n{answer}")
    except Exception as e:
        print(f"Reflection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_10_sentences_v2())
