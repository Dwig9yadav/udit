
import os
from dotenv import load_dotenv

# Load .env from backend folder
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

base_url = os.getenv("HINDSIGHT_BASE_URL")
print(f"HINDSIGHT_BASE_URL: '{base_url}'")
print(f"Length: {len(base_url) if base_url else 0}")
if base_url:
    print(f"Bytes: {base_url.encode('utf-8')}")

api_key = os.getenv("HINDSIGHT_API_KEY")
print(f"API Key present: {bool(api_key)}")

enabled = os.getenv("HINDSIGHT_ENABLED")
print(f"HINDSIGHT_ENABLED: '{enabled}'")
