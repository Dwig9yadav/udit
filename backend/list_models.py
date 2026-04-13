import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Available models:")
for model in client.models.list():
    try:
        print(model.name)
    except Exception as e:
        print(e)
