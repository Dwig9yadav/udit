import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_supabase
from routers.docurag import generate_test

def simulate_generate_test():
    sb = get_supabase()
    resp = sb.table("pdfs").select("id, filename").eq("status", "indexed").limit(1).execute()
    pdf = resp.data[0] if resp.data else None
    if not pdf:
        print("No indexed PDF found for testing.")
        return

    import asyncio
    
    # We must mock the Depends(get_current_user)
    current_user = {"id": "1", "role": "admin"}
    req = {"pdf_id": pdf["id"], "difficulty": "medium"}
    
    try:
        res = asyncio.run(generate_test(req, current_user=current_user))
        print("Success! Output:", str(res)[:500])
    except Exception as e:
        print("Failed with exception:", str(e))

if __name__ == "__main__":
    simulate_generate_test()
