
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("HINDSIGHT_API_KEY")
base_url = "https://api.hindsight.vectorize.io"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

payload = {
    "fact_type": "experience_fact",
    "content": "Testing connection success",
    "metadata": {"source": "test_script"}
}

# Testing the path that gave a 307
url = f"{base_url}/v1/default/banks/user_6/memories/retain/"

print(f"Following redirect for {url}...")

try:
    with httpx.Client(follow_redirects=True) as client:
        response = client.post(url, headers=headers, json=payload, timeout=5)
        print(f"Final URL: {response.url}")
        print(f"Result: {response.status_code}")
        print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
