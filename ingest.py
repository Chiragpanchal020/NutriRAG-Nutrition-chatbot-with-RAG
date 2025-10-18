#ingest.py
# This script is used to ingest data into the database
#Pip install pymupdf tiktoken supabase openai tqdm python-dotenv

import os
import re
import fitz # PyMuPDF
import tiktoken
from supabase import create_client, Client
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv, find_dotenv

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

# Sentence chunking parameters
SENTS_PER_CHUNK = 20
SENT_OVERLAP = 2
MAX_TOKENS = 1300  # safety cap (trim if 10 sentences are too long)
MIN_TOKENS = 50  # skip very tiny fragments

enc = tiktoken.get_encoding("cl100k_base") #matching openai's embedding model

def clean_text(t:str)->str:
    #normalize whitespace and fix hyphenation across line breaks
    t = t.replace("\r", " ") #replace carriage returns with spaces
    t = re.sub(r'-\s*\n\s*', ' ', t) #join "nutri-\n-tion" into "nutrition"
    t = re.sub(r'\s+\n', '\n', t) #collapse multiple spaces to single space
    t = re.sub(r"[ \t]+", ' ', t) #collapse tabs and multiple spaces
    t = t.replace("\n", " ").strip() #collapse newlines and strip whitespace
    return t

def split_sentences(text:str):
    # simple sentence splitter using regex
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sents if s.strip()]

def chunk_page_by_sentences(text: str,
                            sents_per_chunk: int = SENTS_PER_CHUNK,
                            overlap: int = SENT_OVERLAP,
                            max_tokens: int = MAX_TOKENS,
                            min_tokens : int = MIN_TOKENS):
    sents = split_sentences(text)
    i = 0
    step = max(1, sents_per_chunk - overlap)
    while i < len(sents):
        piece = sents[i:i+ sents_per_chunk]
        if not piece:
            break
        chunk = " ".join(piece)

        # enforce token ceiling
        ids = enc.encode(chunk)
        while max_tokens and len(ids) > max_tokens and len(piece) > 1:
            piece = piece[:-1]  # remove last sentence
            chunk = " ".join(piece)
            ids = enc.encode(chunk)

        if len(ids) >= min_tokens:
            yield chunk
        i += step

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
    inputs, metas = [], []
    print("Chunking (10 Sentences per chunk, 2 Overlap)...")
    for page, text in pages:
        if not text:
            continue
        for chunk in chunk_page_by_sentences(text):
            inputs.append(chunk)
            metas.append({"page": page, "source": PDF_PATH})

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

    print(f"🥳 Done!! Insterted {len(rows)} chunks for doc_id = {DOC_ID}")

if __name__ == "__main__":
    main()



        


