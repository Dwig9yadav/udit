import urllib.request, json

data = {
    "name": "Admin",
    "institution_id": "123123",
    "password": "123123", # Password MUST be minimum 6 digits in this system!
    "role": "admin",
    "avatar": "male"
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/auth/register",
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req) as response:
        print("Successfully created Admin!")
except urllib.error.HTTPError as e:
    print(f"Error: {e.read().decode()}")
