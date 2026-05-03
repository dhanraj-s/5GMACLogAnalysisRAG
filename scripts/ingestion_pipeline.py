import os
import sys
import json
import pickle
from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyMuPDFLoader
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

# --- Load Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../configs/config.json')

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"[!] Error: Configuration file not found at {CONFIG_PATH}")
    print("[!] Please create the configuration file before running.")
    sys.exit(1)

# Extract parameters from config
OLLAMA_ADDR = config.get('OLLAMA_ADDR', 'http://localhost:11434')
EMBEDDING_MODEL = config.get('EMBEDDING_MODEL', 'qwen3-embedding:4b')

# Resolve input and database paths relative to this script's location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Note: The ingestion pipeline reads the *output* of the markdown converter
INPUT_DIR_RAW = config.get('DOCS_OUTPUT_DIR', '../rag_docs_md')
DB_DIR_RAW = config.get('DB_DIR', '../db')

INPUT_DIR = os.path.normpath(os.path.join(BASE_DIR, INPUT_DIR_RAW))
DB_DIR = os.path.normpath(os.path.join(BASE_DIR, DB_DIR_RAW))

PERSIST_DIRECTORY = os.path.join(DB_DIR, 'chroma_db')
CHUNKS_PATH = os.path.join(DB_DIR, 'chunks.pkl')

def load_documents(input_path=INPUT_DIR):
    '''Load all files from the docs_md directory'''
    print(f'[*] Loading documents from {input_path}...')

    if not os.path.exists(input_path):
        print(f"\n[!] Error: The directory {input_path} does not exist.")
        print("[!] Please run the document conversion script first to generate the markdown files.\n")
        sys.exit(1)
    
    loader = DirectoryLoader(
        path=input_path,
        glob='*.md',
        loader_cls=TextLoader
    )

    documents = loader.load()

    if len(documents) == 0:
        print(f"\n[!] Error: No markdown files found in {input_path}.")
        print("[!] Please run the document conversion script first.\n")
        sys.exit(1)
    
    for i, doc in enumerate(documents):
        print(f'Document {i+1}')
        print(f'    Source: {doc.metadata.get("source", "unknown")}')
        print(f'    Content length: {len(doc.page_content)} characters')
        print(f'    Content preview: {doc.page_content[:100]}...')
        print(f'    metadata: {doc.metadata}')

    return documents

def split_documents(documents):
    headers_to_split_on = [
        ('##', 'Header 2'),
        ('###', 'Header 3'),
        ('####', 'Header 4'),
        ('#####', 'Header 5'),
        ('######', 'Header 6')
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False
    )

    chunks = []

    section_filter = [
        '5G; NR; Medium Access Control (MAC) protocol specification (3GPP TS 38.321 version 16.1.0 Release 16)',
        'ETSI',
        'Important notice',
        'Copyright Notification',
        'Intellectual Property Rights',
        'Essential patents',
        'Trademarks',
        'Legal Notice',
        'Modal verbs terminology',
        'Contents',
        'Foreword',
        '1 Scope',
        '2 References',
        'ETSI TS 138 321 V16.1.0 (2020-07)',
        'Annex A (informative): Change history'
    ]

    section_filter = [s.lower() for s in section_filter]

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=5000,
        chunk_overlap=500
    )

    print('[*] Splitting documents...')
    for doc in documents:
        doc_chunks = markdown_splitter.split_text(doc.page_content)

        for chunk in doc_chunks:
            chunk.metadata = {**doc.metadata, **chunk.metadata}
            chunk_title = str(chunk.metadata.get('Header 2', '')).strip()

            if chunk_title.lower() not in section_filter:
                sub_chunks = char_splitter.split_documents([chunk])
                for sub_chunk in sub_chunks:
                    sub_chunk.metadata = chunk.metadata 
                    chunks.append(sub_chunk)

    if len(chunks) > 0:
        for i, chunk in enumerate(chunks):
            print(f'\n--- Chunk {i+1} ---')
            print(f'Source: {chunk.metadata.get("source", "unknown")}')
            print(f'Length: {len(chunk.page_content)} characters')
            print(f'Content:')
            print(chunk.page_content[:200] + " ... [Truncated]") # Truncated to avoid flooding console
            print('-'*50)
    
    return chunks

def create_vector_store(chunks, persist_directory=PERSIST_DIRECTORY):
    embedding_model = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_ADDR
    )

    print(f'[*] Embedding {len(chunks)} chunks using {EMBEDDING_MODEL}. Might take a while...')
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=persist_directory,
        collection_metadata={'hnsw:space':'cosine'}
    )
    
    print(f'[*] Vector store successfully created and saved to {persist_directory}.')
    return vectorstore

def save_chunks(chunks, path=CHUNKS_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(chunks, f)
    print(f'[*] BM25 Chunks saved to {path}.')

def main():
    documents = load_documents()
    chunks = split_documents(documents)
    vectorstore = create_vector_store(chunks)
    save_chunks(chunks)
    print("\n[*] Ingestion Pipeline Completed Successfully!")

if __name__ == '__main__':
    main()