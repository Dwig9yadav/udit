import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

# We need the admin token to perform indexing
admin_institution_id = "123123"
admin_password = "123"

# wait, password was updated to "123123" in previous session? The user said "create a admin with id- 123123 and password 123", but the backend limit was 6 characters, so the password was set to "123123" by the previous agent.
# Let's try 123123
def test_indexing():
    base_url = "http://127.0.0.1:8000/api"
    
    with httpx.Client(timeout=60.0) as client:
        # Login
        login_res = client.post(f"{base_url}/auth/login", json={
            "institution_id": admin_institution_id,
            "password": "123"
        })
        if login_res.status_code != 200:
            print("Login with 123 failed, trying 123123...")
            login_res = client.post(f"{base_url}/auth/login", json={
                "institution_id": admin_institution_id,
                "password": "123123"
            })
            if login_res.status_code != 200:
                print("Login failed:", login_res.text)
                return
            
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get PDFs
        pdfs_res = client.get(f"{base_url}/rag/pdfs", headers=headers)
        pdfs = pdfs_res.json()
        print(f"Found {len(pdfs)} PDFs")
        
        for pdf in pdfs:
            if pdf["status"] != "indexed":
                print(f"Attempting to index PDF: {pdf['filename']} (ID: {pdf['id']})")
                index_res = client.post(f"{base_url}/rag/pdfs/{pdf['id']}/index", headers=headers)
                print(f"Status Code: {index_res.status_code}")
                print(f"Response: {index_res.text}")

if __name__ == "__main__":
    test_indexing()
