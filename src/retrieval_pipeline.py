import os
import sys
import json
import pickle
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

# --- Load Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../configs/config.json')

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"Error: Configuration file not found at {CONFIG_PATH}")
    print("Please create the configuration file before running.")
    sys.exit(1)

# Extract parameters from config
OLLAMA_ADDR = config.get('OLLAMA_ADDR', 'http://localhost:11434')
EMBEDDING_MODEL = config.get('EMBEDDING_MODEL', 'qwen3-embedding:4b')

# Resolve database paths relative to this script's location
DB_DIR = config.get('DB_DIR', '../db')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOLVED_DB_DIR = os.path.normpath(os.path.join(BASE_DIR, DB_DIR))

PERSIST_DIR = os.path.join(RESOLVED_DB_DIR, 'chroma_db')
CHUNKS_PATH = os.path.join(RESOLVED_DB_DIR, 'chunks.pkl')

def load_retriever(
    persist_dir=PERSIST_DIR,
    chunks_path=CHUNKS_PATH,
    k=5,
    score_threshold=0.3,
    bm25_weight=0.3,
    vector_weight=0.7
):
    # --- Graceful Exit Checks ---
    if not os.path.exists(chunks_path):
        print(f"\n[!] Error: Required chunks file not found at: {chunks_path}")
        print("[!] Please run `scripts/ingestion_pipeline.py` to build the database before attempting retrieval.\n")
        sys.exit(1)
        
    if not os.path.exists(persist_dir):
        print(f"\n[!] Error: Chroma vector database not found at: {persist_dir}")
        print("[!] Please run `scripts/ingestion_pipeline.py` to build the database before attempting retrieval.\n")
        sys.exit(1)

    print('Loading chunks for BM25...')
    with open(chunks_path, 'rb') as f:
        chunks = pickle.load(f)
    print(f'Loaded {len(chunks)} chunks.')

    print('Loading vector store...')
    embedding_model = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_ADDR
    )
    db = Chroma(
        persist_directory=persist_dir,
        embedding_function=embedding_model,
        collection_metadata={"hnsw:space": "cosine"}
    )

    vector_retriever = db.as_retriever(
        search_type='similarity_score_threshold',
        search_kwargs={"k": k, "score_threshold": score_threshold}
    )

    print('Building BM25 retriever...')
    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = k

    hybrid_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[bm25_weight, vector_weight]
    )

    print('Hybrid retriever ready.')
    return hybrid_retriever

def retrieve(query, retriever):
    print(f'\nQuery: "{query}"')
    docs = retriever.invoke(query)
    print(f'Retrieved {len(docs)} documents.\n')
    print('--- Context ---')
    for i, doc in enumerate(docs, 1):
        print(f'Document {i}:')
        print(f'  Source:  {doc.metadata.get("source", "unknown")}')
        print(f'  Section: {doc.metadata.get("Header 2", "")} / {doc.metadata.get("Header 3", "")}')
        print(f'  Content: {doc.page_content}')
        print()
    return docs

if __name__ == '__main__':
    retriever = load_retriever()
    query = "DTX on pucch in MAC logs"
    retrieve(query, retriever)