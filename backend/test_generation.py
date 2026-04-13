import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_supabase
from routers.rag import _get_gemini_client

def test_generation():
    sb = get_supabase()
    # Find any indexed PDF
    resp = sb.table("pdfs").select("id, filename").eq("status", "indexed").limit(1).execute()
    pdf = resp.data[0] if resp.data else None
    
    if not pdf:
        print("No indexed PDF found.")
        return
        
    print(f"Testing generation for PDF: {pdf['filename']} (ID: {pdf['id']})")
    pdf_id = pdf['id']
    
    chunk_resp = sb.table("pdf_chunks").select("content, page_number").eq("pdf_id", pdf_id).limit(20).execute()
    chunks = chunk_resp.data or []
    
    context = "\n\n".join(f"[Page {c.get('page_number', '?')}] {c.get('content', '')}" for c in chunks)
    prompt = f"Summarize this in one JSON object: {context[:500]}"
    
    client = _get_gemini_client()
    model = "models/gemini-2.0-flash" 
    # try running without 'models/' since they used gemini-2.0-flash
    model_str = os.getenv("GEMINI_GENERATION_MODEL", "gemini-2.0-flash")
    
    print(f"Trying model: {model_str}")
    try:
        response = client.models.generate_content(model=model_str, contents=prompt)
        print("Success! Output:", response.text)
    except Exception as e:
        print("Failed:", str(e))

if __name__ == "__main__":
    test_generation()
