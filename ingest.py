#ingest.py
# This script is used to ingest data into the database
#Pip install pymupdf tiktoken supabase openai tqdm python-dotenv langchain

import os
import re
import fitz # PyMuPDF
import tiktoken
from supabase import create_client, Client
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv, find_dotenv
from langchain_text_splitters  import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

#Config
PDF_PATH = "Human-Nutrition-text.pdf"
DOC_ID = "nutrition-v1"  #keep this stable to avoid duplicate entries
EMBED_MODEL = "text-embedding-3-small"  #1536 dim vectors
BATCH_EMBED = 100
BATCH_INSERT = 200

enc = tiktoken.get_encoding("cl100k_base") #matching openai's embedding model

def clean_text(t:str)->str:
    #normalize whitespace and fix hyphenation across line breaks
    t = t.replace("\r", " ") #replace carriage returns with spaces
    t = re.sub(r'-\s*\n\s*', '', t) #join "nutri-\n-tion" into "nutrition"
    t = re.sub(r'\s+\n', '\n', t) #collapse multiple spaces to single space
    t = re.sub(r"[ \t]+", ' ', t) #collapse tabs and multiple spaces
    t = t.replace("\n", " ").strip() #collapse newlines and strip whitespace
    return t

def pdf_pages(path:str):
    ''' Yield (page_number_1based, cleanded text)'''
    doc = fitz.open(path)
    try:
        for i in range(len(doc)):
            txt = doc[i].get_text("text") or ""
            yield (i +1, clean_text(txt))

    finally:
        doc.close()

def main():
    sb : Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    client = OpenAI(api_key = OPENAI_API_KEY)

    # Optional: keep the table clean for this document
    sb.table("chunks").delete().eq("doc_id", DOC_ID).execute()

    print("Reading PDF by pages...")
    pages=list(pdf_pages(PDF_PATH))

    #Build chunks with page metadata
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,  # Smaller chunks for more precise matching
        chunk_overlap=200,  # Larger overlap to maintain context
        length_function=len,
        is_separator_regex=False,
        separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""]  # Better text splitting
    )

    inputs, metas = [], []
    print("Chunking with RecursiveCharacterTextSplitter...")
    for page_num, text in pages:
        if not text:
            continue
        # The splitter returns a list of documents, we need the content
        page_chunks = text_splitter.create_documents([text])
        for chunk in page_chunks:
            inputs.append(chunk.page_content)
            metas.append({"page": page_num, "source": PDF_PATH})


    print(f"✅ Built {len(inputs)} chunks from {PDF_PATH}")

    #Generate Embeddings 
    vectors = []
    print("Genrating embeddings....")
    for i in tqdm(range(0, len(inputs), BATCH_EMBED), desc= "Embeddings"):
        batch = inputs[i:i + BATCH_EMBED]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors.extend([d.embedding for d in resp.data])

    # Prepare rows
    rows =[]
    for idx, (content, emd, meta) in enumerate(zip(inputs, vectors, metas)):
        rows.append({
            "doc_id": DOC_ID,
            "chunk_index": idx,
            "content": content,
            "metadata": meta,
            "embedding": emd
        })
    print("Uploading to Supabase...")
    for j in tqdm(range(0, len(rows), BATCH_INSERT), desc = "Uploading"):
        sb.table("chunks").insert(rows[j:j + BATCH_INSERT]).execute()

    print(f"✅ Done!! Insterted {len(rows)} chunks for doc_id = {DOC_ID}")

if __name__ == "__main__":
    main()
