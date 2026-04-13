
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("HINDSIGHT_API_KEY")
base_url = "https://api.hindsight.vectorize.io"
headers = {
    "Authorization": f"Bearer {api_key}"
}

endpoints = [
    "/v1/health",
    "/v1/status",
    "/v1/default/status",
    "/v1/default/banks",
]

print(f"Testing Hindsight Health/Status endpoints...")

for ep in endpoints:
    try:
        url = f"{base_url}{ep}"
        print(f"\nChecking: GET {url}")
        response = httpx.get(url, headers=headers, timeout=5)
        print(f"Result: {response.status_code}")
        if response.status_code < 400:
            print(f"SUCCESS! Body: {response.text}")
        else:
            print(f"Error Body: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")
