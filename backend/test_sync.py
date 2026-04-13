import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_supabase
from routers.rag import _download_pdf_from_storage

def test_index_locally():
    sb = get_supabase()
    resp = sb.table("pdfs").select("*").eq("status", "failed").limit(1).execute()
    pdf = resp.data[0] if resp.data else None
    
    if not pdf:
        print("No failed PDF found.")
        return
        
    print(f"Testing PDF: {pdf['filename']}")
    try:
        tmp_path = _download_pdf_from_storage(sb, pdf["storage_path"])
        print(f"Downloaded to {tmp_path}")
    except Exception as e:
        print(f"Failed to download: {e}")
        return
        
    from pypdf import PdfReader
    reader = PdfReader(tmp_path)
    total_pages = len(reader.pages)
    print(f"Total pages in PDF: {total_pages}")
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        print(f"Extracted page {i+1}, text len: {len(text) if text else 0}")
        if i >= 5:
            print("Stopping after 5 pages.")
            break

if __name__ == "__main__":
    test_index_locally()
