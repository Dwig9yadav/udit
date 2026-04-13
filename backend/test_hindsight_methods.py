
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

# Testing the most promising path with variations
path = "/v1/default/banks/user_6/memories/retain"

tests = [
    ("POST", path),
    ("POST", path + "/"),
    ("PUT", path),
    ("PUT", path + "/"),
]

print(f"Testing Hindsight variations for {path}...")

for method, url_path in tests:
    try:
        url = f"{base_url}{url_path}"
        print(f"\nChecking: {method} {url}")
        if method == "POST":
            response = httpx.post(url, headers=headers, json=payload, timeout=5)
        else:
            response = httpx.put(url, headers=headers, json=payload, timeout=5)
            
        print(f"Result: {response.status_code}")
        if response.status_code < 400:
            print(f"SUCCESS! Body: {response.text}")
        else:
            print(f"Error Body: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")
