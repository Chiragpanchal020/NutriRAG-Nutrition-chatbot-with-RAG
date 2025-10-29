import os
import textwrap
from supabase import create_client, Client
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

#Config
PDF_PATH = "Human-Nutrition-text.pdf"
EMBED_MODEL = "text-embedding-3-small"  #1536 dim vectors
TOP_K = 3

queries = [
    "What are the six classes of nutrients essential for the human body?",
    "How does saliva help with digestion?"
]

def main():
    sb : Client = create_client(SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY)
    client = OpenAI(api_key=OPENAI_API_KEY)

    for q in queries:
        # embed queries
        e = client.embeddings.create(model=EMBED_MODEL,input=q).data[0].embedding

        # call your RPC with a metadata filter on this PDF
        resp = sb.rpc("match_documents",{
            "query_embedding": e,
            "match_count": TOP_K,
            "filter": {"source": PDF_PATH}
        }).execute()

        rows = resp.data or []
        print("\n" + "=" * 90)
        print(f"QUERY: {q}")
        if not rows:
            print(" (No matches)")
            continue
        
        for rank, r in enumerate(rows,start=1):
            page = (r.get("metadata") or {}).get("Page", "?")
            sim = r.get("similarity", None) 
            sim_str = f"{sim: .3f}" if isinstance(sim, (int,float)) else "?"
            preview = textwrap.shorten(r.get("content","").replace("\n"," "),width=500)
            print(f"  [{rank}] page {page}  sim = {sim_str}   chunk_index={r.get('chunk_index', '?')} ")
            print(f"       {preview}")

if __name__ == "__main__":
    main()
