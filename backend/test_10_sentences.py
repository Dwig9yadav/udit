
import asyncio
import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

# Load .env from backend folder
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

async def test_10_sentences():
    api_key = os.getenv("HINDSIGHT_API_KEY")
    base_url = os.getenv("HINDSIGHT_BASE_URL") or "https://api.hindsight.vectorize.io"
    
    client = Hindsight(api_key=api_key, base_url=base_url)
    bank_id = "udit"
    
    sentences = [
        "First, the user woke up at 7 AM.",
        "Second, the user drank a large cup of black coffee.",
        "Third, the user started debugging a React application.",
        "Fourth, the user found a bug in the Hindsight integration.",
        "Fifth, the user fixed the SDK version from 0.5.0 to 0.1.0.",
        "Sixth, the user had a sandwich for lunch at 1 PM.",
        "Seventh, the user wrote a multi_replace_file_content tool call.",
        "Eighth, the user successfully tested the AI reflection.",
        "Ninth, the user asked to test the system on 10 sentences.",
        "Tenth, the user is now observing this awesome automated test."
    ]
    
    print("--- Ingesting 10 Sentences ---")
    for idx, sentence in enumerate(sentences):
        try:
            res = await client.aretain(
                bank_id=bank_id,
                content=sentence,
                metadata={"source": "bulk_test", "order": str(idx)}
            )
            print(f"Retained {idx + 1}: {sentence[:30]}...")
        except Exception as e:
            print(f"Failed to retain {idx + 1}: {e}")
            
    print("\n--- Reflecting on the 10 Sentences ---")
    try:
        response = await client.areflect(
            bank_id=bank_id,
            query="Summarize the 10 steps of what the user did today.",
            context="You are a helpful assistant. Use all the recent numbered steps."
        )
        answer = getattr(response, 'text', getattr(response, 'answer', "No answer found"))
        print(f"\nAI Reflection Result:\n{answer}")
    except Exception as e:
        print(f"Reflection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_10_sentences())
