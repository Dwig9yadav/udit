import os

env_path = 'c:/Users/Udit Bhatt/OneDrive/Desktop/DocuRag/DOCURAG-main/backend/.env'
with open(env_path, 'r') as f:
    content = f.read()

if "GROQ_API_KEY=" not in content:
    content += "\nGROQ_API_KEY=your_groq_api_key_here\n"

with open(env_path, 'w') as f:
    f.write(content)

print(".env updated with GROQ_API_KEY")
