import re
from langchain_ollama import ChatOllama
from retrieval_pipeline import load_retriever
from mine_logs import get_scored_events, clean_log_line

LLM_MODEL = 'gemma4:latest'
OLLAMA_ADDR = 'http://localhost:11434'
LOG_FILE = 'log_files/du_mac_logs_3.txt'

def build_rag_query(scored_events, top_n=5):
    top5 = scored_events[:top_n]

    cleaned = [
        re.sub(r'<[^>]+>', '', template).strip()
        for template, score in top5
    ]

    return ' '.join(cleaned)


def format_top5(scored_events, top_n=5):
    top5 = scored_events[:top_n]
    lines = []
    for i, (template, score) in enumerate(top5, 1):
        lines.append(f"{i}. {template}")
    return '\n'.join(lines)

def load_log(log_filename):
    with open(log_filename, 'r') as f:
        raw = f.read()
    cleaned_lines = [
        clean_log_line(line)
        for line in raw.split('\n')
        if line.strip()
    ]
    return '\n'.join(cleaned_lines)


def build_prompt(top5_str, context_docs, log_segment):

    if context_docs is not None:
        context_str = '\n\n'.join([
            f"[Source: {doc.metadata.get('source', 'unknown')} | "
            f"Section: {doc.metadata.get('Header 2', '')} / {doc.metadata.get('Header 3', '')}]\n"
            f"{doc.page_content}"
            for doc in context_docs
        ])

        return f"""
        MAC LAYER LOGS:
        {log_segment}

        RELEVANT CONTEXT (3GPP 38.321 + OAI MAC):
        {context_str}

        FIVE ANOMALOUS EVENTS DETECTED:
        {top5_str}

        Find the root cause event from the five events listed above. Analyze the root cause event error and trace its impact on subsequent connection quality. Build a causal chain.
        """
        # Pick the most relevant one of the five events above as the key event. Analyze the key event error and trace its impact on subsequent connection quality. Build a causal chain.
    else:
        return f"""     
        MAC LAYER LOGS:
        {log_segment}

        FIVE ANOMALOUS EVENTS DETECTED:
        {top5_str}

        Find the root cause event from the five events listed above. Analyze the root cause event error and trace its impact on subsequent connection quality. Build a causal chain.
        """

def run_pipeline(log_filename=LOG_FILE, use_rag=True):
    print('Analyzing logs...')
    scored_events = get_scored_events(log_filename)
    top5_str = format_top5(scored_events)
    print(f'Top 5 events:\n{top5_str}\n')
    log_segment = load_log(log_filename)
    if use_rag:
        rag_query = build_rag_query(scored_events)
        print(f'RAG query: {rag_query}\n')

        print('Retrieving spec context...')
        retriever = load_retriever()
        context_docs = retriever.invoke(rag_query)
        print(f'Retrieved {len(context_docs)} chunks.\n')

        print(f'--- Retrieved {len(context_docs)} chunks ---')
        for i, doc in enumerate(context_docs, 1):
            print(f'\nChunk {i}:')
            print(f'  Source:  {doc.metadata.get("source", "unknown")}')
            print(f'  Header2: {doc.metadata.get("Header 2", "")}')
            print(f'  Header3: {doc.metadata.get("Header 3", "")}')
            print(f'  Length:  {len(doc.page_content)} chars')
            print(f'  Preview: {doc.page_content}')
            print('-' * 50)

        prompt = build_prompt(top5_str, context_docs, log_segment)
    
    else:
        prompt = build_prompt(top5_str, None, log_segment)

    print('Calling LLM...')
    llm = ChatOllama(
        model=LLM_MODEL,
        base_url=OLLAMA_ADDR,
        temperature=0,
        # additional_kwargs={
        #     "chat_template_kwargs": {"enable_thinking": False}
        # }
    )

    response = llm.invoke(prompt)
    print('\n--- RCA Output ---')
    print(response.content)

    return response.content

if __name__ == '__main__':
    run_pipeline(use_rag=False)