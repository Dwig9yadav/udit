
import asyncio
import os
from dotenv import load_dotenv
from hindsight_client import Hindsight

# Load .env from backend folder
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

async def test_hindsight():
    api_key = os.getenv("HINDSIGHT_API_KEY")
    base_url = os.getenv("HINDSIGHT_BASE_URL") or "https://api.hindsight.vectorize.io"
    
    print(f"Testing Hindsight SDK with Base URL: {base_url}")
    print(f"API Key present: {bool(api_key)}")
    
    if not api_key:
        print("Error: HINDSIGHT_API_KEY not found in .env")
        return

    client = Hindsight(api_key=api_key, base_url=base_url)
    bank_id = "udit" # From the health check we know this bank exists
    
    print(f"\n--- Testing RETAIN ---")
    try:
        result = await client.aretain(
            bank_id=bank_id,
            content="The user is testing the Hindsight integration today.",
            metadata={"source": "test_sdk_script", "topic": "integration"}
        )
        print(f"Retain Success: {result}")
    except Exception as e:
        print(f"Retain Failed: {e}")

    print(f"\n--- Testing RECALL ---")
    try:
        response = await client.arecall(
            bank_id=bank_id,
            query="What is the user doing today?",
        )
        # Check standard results attribute
        memories = response.results if hasattr(response, 'results') else []
        print(f"Recall Found {len(memories)} memories.")
        for i, m in enumerate(memories):
            # Try to get content attribute or use string representation
            content = getattr(m, 'content', str(m))
            print(f"  [{i}] {content}")
    except Exception as e:
        print(f"Recall Failed: {e}")

    print(f"\n--- Testing REFLECT ---")
    try:
        # Reflect usually takes context or mission
        response = await client.areflect(
            bank_id=bank_id,
            query="Summarize what you know about the user's current activity.",
            context="You are a helpful memory assistant."
        )
        answer = response.answer if hasattr(response, 'answer') else str(response)
        print(f"Reflect Answer: {answer}")
    except Exception as e:
        print(f"Reflect Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_hindsight())
