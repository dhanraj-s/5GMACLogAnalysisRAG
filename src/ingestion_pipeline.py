import os, pickle
from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyMuPDFLoader
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

INPUT_DIR = 'docs_md/'

EMBEDDING_MODEL = 'qwen3-embedding:4b'
OLLAMA_ADDR = 'http://localhost:11434'
CHUNKS_PATH = 'db/chunks.pkl'

def load_documents(input_path = INPUT_DIR):
    '''Load all files from the docs_md directory'''

    print(f'Loading documents from {INPUT_DIR}...')

    if not os.path.exists(INPUT_DIR):
        raise FileNotFoundError(\
            f'The directory {INPUT_DIR} containing markdown files does not exist.'+\
            f'Please create md files from source docs using script convert_to_markdown.py.'\
        )
    
    loader = DirectoryLoader(
        path = INPUT_DIR,
        glob = '*.md',
        loader_cls = TextLoader
    )

    documents = loader.load()

    if len(documents) == 0:
        raise FileNotFoundError(f'No files found in {INPUT_DIR}. Please generate md files using script convert_to_markdown.py')
    
    for i,doc in enumerate(documents):
        print(f'Document {i+1}')
        print(f'    Source: {doc.metadata['source']}')
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
        headers_to_split_on = headers_to_split_on,
        strip_headers = False
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

    for doc in documents:

        doc_chunks = markdown_splitter.split_text(doc.page_content)

        for chunk in doc_chunks:

            chunk.metadata = {**doc.metadata, **chunk.metadata}

            chunk_title = str(chunk.metadata.get('Header 2', '').strip())

            if chunk_title.lower() not in section_filter:
                sub_chunks = char_splitter.split_documents([chunk])
                for sub_chunk in sub_chunks:
                    sub_chunk.metadata = chunk.metadata 
                    chunks.append(sub_chunk)


    if len(chunks) > 0:

        for i,chunk in enumerate(chunks):
            print(f'\n--- Chunk{i+1} ---')
            print(f'Source: {chunk.metadata['source']}')
            print(f'Length: {len(chunk.page_content)} characters')
            print(f'Content:')
            print(chunk.page_content)
            print('-'*50)
    
    return chunks

def create_vector_store(chunks, persist_directory='db/chroma_db'):

    embedding_model = OllamaEmbeddings(
        model = EMBEDDING_MODEL,
        base_url = OLLAMA_ADDR
    )

    print(f'Embedding {len(chunks)} chunks. Might take a while...')
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=persist_directory,
        collection_metadata={'hnsw:space':'cosine'}
    )
    print(f'Vector store created.')

    print(f'Vector store saved to {persist_directory}.')

    return vectorstore


def save_chunks(chunks, path=CHUNKS_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(chunks, f)
    print(f'Chunks saved to {path}.')


def main():
    documents = load_documents()
    chunks = split_documents(documents)
    vectorstore = create_vector_store(chunks)
    save_chunks(chunks)

    

if __name__ == '__main__':
    main()
