import os

env_path = 'c:/Users/Udit Bhatt/OneDrive/Desktop/DocuRag/DOCURAG-main/backend/.env'
with open(env_path, 'r') as f:
    content = f.read()

content = content.replace('GEMINI_GENERATION_MODEL_FALLBACK=gemini-1.5-flash', 'GEMINI_GENERATION_MODEL_FALLBACK=gemini-2.0-flash-lite')
content = content.replace('GEMINI_GENERATION_MODEL=gemini-2.0-flash', 'GEMINI_GENERATION_MODEL=gemini-2.5-flash')

with open(env_path, 'w') as f:
    f.write(content)

print(".env updated successfully")
