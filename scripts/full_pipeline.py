import re
import collections
import numpy as np
import argparse
import os
import sys
import json
import plotly.express as px
from sklearn.manifold import TSNE
from langchain_ollama import ChatOllama, OllamaEmbeddings
from sklearn.cluster import AgglomerativeClustering
from groq import Groq

# --- System Path Setup ---
# Works perfectly from the 'scripts/' directory
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# --- Project Imports ---
from src.retrieval_pipeline import load_retriever
from src.mine_logs import get_scored_events as get_scored_events_static
from src.mine_logs import clean_log_line
from src.mine_logs_dynamic_2 import get_scored_events as get_scored_events_dynamic

# --- Load Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../configs/config.json')

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"Error: Configuration file not found at {CONFIG_PATH}")
    print("Please create the file according to the instructions.")
    exit(1)

OLLAMA_ADDR = config.get('OLLAMA_ADDR', 'http://localhost:11434')
EMBEDDING_MODEL = config.get('EMBEDDING_MODEL', 'qwen3-embedding:4b')
GROQ_MODEL = config.get('GROQ_MODEL', 'llama3.3-70b-versatile')
RESULTS_DIR = config.get('RESULTS_DIR', '../results')
NUM_CLUSTERS = config.get('NUM_CLUSTERS', 15)
DEFAULT_LOG_FILE = config.get('DEFAULT_LOG_FILE', '../log_files/du_mac_logs_3.txt')
DEFAULT_GROQ_LOG_FILE = config.get('DEFAULT_GROQ_LOG_FILE', '../log_files/du_mac_logs_3.txt')
DEFAULT_LLM_MODEL = config.get('DEFAULT_LLM_MODEL', 'gemma4:latest')

# --- Helper Functions ---

def get_top5_from_clustering(log_filename, results_dir):
    """
    Extracts the top 5 anomalous events using isolation/clustering logic,
    and generates a 2D t-SNE HTML visualization saved in results_dir.
    """
    with open(log_filename, 'r', encoding='utf-8') as f:
        raw = f.read()
        
    log_lines = [clean_log_line(line) for line in raw.split('\n') if line.strip() != '']
    
    print(f"[*] Generating sentence embeddings via Ollama for clustering (Model: {EMBEDDING_MODEL})...")
    embedding_model = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_ADDR)
    vectors = embedding_model.embed_documents(log_lines)
    X = np.array(vectors)

    print(f"[*] Grouping logs into {NUM_CLUSTERS} clusters...")
    clusterer = AgglomerativeClustering(n_clusters=NUM_CLUSTERS, linkage='ward')
    cluster_labels = clusterer.fit_predict(X)

    cluster_counts = collections.Counter(cluster_labels)
    sorted_clusters = sorted(cluster_counts.items(), key=lambda x: x[1])
    top_5_smallest = sorted_clusters[:5]

    top_events = []
    for cluster_id, size in top_5_smallest:
        logs_in_cluster = [
            log_lines[i] for i, label in enumerate(cluster_labels) 
            if label == cluster_id
        ]
        majority_log = collections.Counter(logs_in_cluster).most_common(1)[0][0]
        top_events.append((majority_log, size))
        
    print('[*] Running t-SNE dimensionality reduction for visualization...')
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    tsne_results = tsne.fit_transform(X)

    plot_data = {
        'X_Coordinate': tsne_results[:, 0],
        'Y_Coordinate': tsne_results[:, 1],
        'Log_Text': log_lines,
        'Line_Number': [i+1 for i in range(len(log_lines))],
        "Cluster": [f"Cluster {label}" for label in cluster_labels]
    }

    print('[*] Generating interactive plot...')
    fig = px.scatter(
        plot_data,
        x='X_Coordinate',
        y='Y_Coordinate',
        color="Cluster",
        hover_data={'Log_Text': True, 'Line_Number': True, 'X_Coordinate': False, 'Y_Coordinate': False},
        title=f't-SNE visualization of MAC log vectors'
    )

    fig.update_traces(marker=dict(size=5, opacity=0.7))

    output_file = os.path.join(results_dir, "tsne_visualization.html")
    fig.write_html(output_file)
    print(f"[*] Success! Interactive cluster plot saved to {output_file}")
        
    return top_events

def build_rag_query(scored_events, top_n=5):
    top5 = scored_events[:top_n]
    cleaned = [
        re.sub(r'<[^>]+>', '', template).strip()
        for template, score in top5
    ]
    return ' '.join(cleaned)

def generate_english_rag_query(log_segment, mode_name, results_dir):
    """Uses Groq to translate raw logs directly into a plain English semantic query with cross-mode caching."""
    
    # Save the shared cache in the parent directory so modes 3, 6, 9, 12 can all find it
    shared_query_filename = os.path.join(os.path.dirname(results_dir), "shared_translated_query.txt")
    mode_specific_filename = os.path.join(results_dir, f"{mode_name}_translated_query.txt")
    
    # 1. Check if the shared cache already exists for this specific log file
    if os.path.exists(shared_query_filename):
        print(f"[*] Shared translated query found. Reusing to save API credits...")
        with open(shared_query_filename, 'r', encoding='utf-8') as f:
            query = f.read().strip()
            
        # Create a mode-specific copy so your artifacts remain consistent
        with open(mode_specific_filename, 'w', encoding='utf-8') as f:
            f.write(query)
            
        print(f"[*] Copied cached query to {mode_specific_filename}")
        return query
            
    # 2. If no shared cache exists, call Groq API
    print(f"[*] Contacting Groq API ({GROQ_MODEL}) to translate logs to an English query...")
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    prompt = f"""
    You are an expert telecommunications network engineer.
    Your task is to analyze the provided MAC layer logs, identify the most critical errors or anomalies, and translate them into a single, plain English search query. This query will be used in a semantic vector database to find relevant 3GPP specifications and OAI MAC documentation.

    Instructions:
    1. Scan the logs and explicitly attend to the most important error events.
    2. Consider and mention any sudden changes or degradations in various metrics (e.g., CQI, MCS, timeouts).
    3. Output ONLY the finalized search query string. Do not include conversational text, quotes, or explanations.

    RAW MAC LOGS:
    {log_segment}
    """
    
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    query = response.choices[0].message.content.strip()
    
    # 3. Save BOTH the shared cache file and the mode-specific artifact
    with open(shared_query_filename, 'w', encoding='utf-8') as f:
        f.write(query)
        
    with open(mode_specific_filename, 'w', encoding='utf-8') as f:
        f.write(query)
        
    print(f"[*] Saved translated query to {mode_specific_filename} and cached as shared file.")
    
    return query

def format_top5(scored_events, top_n=5):
    top5 = scored_events[:top_n]
    lines = []
    for i, (template, score) in enumerate(top5, 1):
        lines.append(f"{i}. {template}")
    return '\n'.join(lines)

def load_log(log_filename):
    with open(log_filename, 'r', encoding='utf-8') as f:
        raw = f.read()
    cleaned_lines = [
        clean_log_line(line)
        for line in raw.split('\n')
        if line.strip()
    ]
    return '\n'.join(cleaned_lines)

# --- Prompt Builders ---

def build_baseline_prompt(log_segment, context_docs):
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

        Analyze the wireless link quality from all of the given MAC layer logs and suggest improvement strategies.
        """
    else:
        return f"""
        MAC LAYER LOGS:
        {log_segment}

        Analyze the wireless link quality from the given MAC layer logs and suggest improvement strategies.
        """

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
    else:
        return f"""     
        MAC LAYER LOGS:
        {log_segment}

        FIVE ANOMALOUS EVENTS DETECTED:
        {top5_str}

        Find the root cause event from the five events listed above. Analyze the root cause event error and trace its impact on subsequent connection quality. Build a causal chain.
        """

# --- Main Execution Pipeline ---

def run_pipeline(mode, log_filename, llm_model, groq_log_filename=None):
    print(f'\n{"="*50}')
    print(f'--- Initializing Pipeline in MODE {mode} using {llm_model} ---')
    print(f'{"="*50}')
    
    # --- Setup Results Directory Structure ---
    base_log_name = os.path.basename(log_filename)
    clean_log_name = os.path.splitext(base_log_name)[0]
    mode_name = f"mode{mode}"
    
    # Path: ../results/<clean_log_name>/<mode_name>/
    base_results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), RESULTS_DIR, clean_log_name)
    results_dir = os.path.join(base_results_dir, mode_name)
    os.makedirs(results_dir, exist_ok=True)
    
    print(f"[*] Artifacts will be saved to: {results_dir}")
    print(f'Loading logs from {log_filename}...')
    log_segment = load_log(log_filename)

    if groq_log_filename and os.path.exists(groq_log_filename):
        print(f'[*] Loading separate Groq translation logs from {groq_log_filename}...')
        groq_log_segment = load_log(groq_log_filename)
    else:
        groq_log_segment = log_segment
    
    use_rag = mode not in [1, 4, 7, 10]
    if not use_rag:
        rag_tag = "wo_rag"
    elif mode in [2, 5, 8, 11]:
        rag_tag = "with_rag_concat"
    else:
        rag_tag = "with_rag_llm"
        
    scored_events = []
    top5_str = ""
    context_docs = None
    sig_words = []

    # Step 1: Handle Event Extraction Based on Mode
    if mode in [2, 4, 5, 6]:
        print("[*] Analyzing logs using static template miner...")
        scored_events = get_scored_events_static(log_filename)
        
    elif mode in [7, 8, 9]:
        print("[*] Analyzing logs using dynamic template miner (Groq/Chi-Square)...")
        dynamic_out = get_scored_events_dynamic(log_filename, results_dir)
        
        if isinstance(dynamic_out, tuple) and len(dynamic_out) == 2:
            scored_events, sig_words = dynamic_out
        else:
            scored_events = dynamic_out
            sig_words = ["[!] Warning: Update `get_scored_events` in `src/mine_logs_dynamic_2.py` to return tuple!"]
            
        sig_words_filename = os.path.join(results_dir, f"{mode_name}_significant_words.txt")
        with open(sig_words_filename, 'w', encoding='utf-8') as f:
            for word in sig_words:
                f.write(f"{word}\n")
        print(f"[*] Saved significant words to {sig_words_filename}")

    elif mode in [10, 11, 12]:
        print("[*] Analyzing logs using sentence embeddings and clustering...")
        scored_events = get_top5_from_clustering(log_filename, results_dir)

    top5_str = format_top5(scored_events) if scored_events else ""
    if mode not in [1, 2, 3]:
        print(f'\nTop 5 events:\n{top5_str}\n')

    if mode in range(2, 13) and mode != 3:
        events_filename = os.path.join(results_dir, f"{mode_name}_key_events_{rag_tag}.txt")
        with open(events_filename, 'w', encoding='utf-8') as f:
            f.write(top5_str)
        print(f"[*] Saved key events to {events_filename}")

    print(f'\nInitializing local LLM ({llm_model})...')
    llm = ChatOllama(
        model=llm_model,
        base_url=OLLAMA_ADDR,
        temperature=0,
    )

    # Step 2: Handle RAG Retrieval
    if use_rag:
        print('Retrieving spec context...')
        retriever = load_retriever()
        
        if rag_tag == "with_rag_concat":
            print('[*] Using event concatenation for RAG query...')
            rag_query = build_rag_query(scored_events)
            
            rag_query_filename = os.path.join(results_dir, f"{mode_name}_rag_query.txt")
            with open(rag_query_filename, 'w', encoding='utf-8') as f:
                f.write(rag_query)
            print(f"[*] Saved RAG query to {rag_query_filename}")
            
        elif rag_tag == "with_rag_llm":
            print('[*] Using Groq API translation for RAG query...')
            rag_query = generate_english_rag_query(groq_log_segment, mode_name, results_dir)
            
        print(f'RAG query: {rag_query}\n')
        context_docs = retriever.invoke(rag_query)
        print(f'Retrieved {len(context_docs)} chunks.\n')

        chunks_content = []
        for i, doc in enumerate(context_docs, 1):
            source = doc.metadata.get('source', 'unknown')
            h2 = doc.metadata.get('Header 2', '')
            h3 = doc.metadata.get('Header 3', '')
            chunks_content.append(
                f"--- Chunk {i} ---\n"
                f"Source: {source} | Section: {h2} / {h3}\n"
                f"{doc.page_content}\n"
            )
            
        chunks_str = '\n'.join(chunks_content)
        
        # Extract just "concat" or "llm" from the rag_tag
        rag_suffix = "concat" if rag_tag == "with_rag_concat" else "llm"
        chunks_filename = os.path.join(results_dir, f"{mode_name}_chunks_rag_{rag_suffix}.txt")
        
        with open(chunks_filename, 'w', encoding='utf-8') as f:
            f.write(chunks_str)
            
        print(f"[*] Saved retrieved chunks to {chunks_filename}")

    # Step 3: Build Final Prompt
    if mode in [1, 2, 3]:
        prompt = build_baseline_prompt(log_segment, context_docs)
    else:
        prompt = build_prompt(top5_str, context_docs, log_segment)

    # Step 4: Execute Final LLM RCA Request
    print(f'\nExecuting final RCA LLM inference via {llm_model}...')
    response = llm.invoke(prompt)
    
    analysis_filename = os.path.join(results_dir, f"{mode_name}_analysis_{rag_tag}.md")
    with open(analysis_filename, 'w', encoding='utf-8') as f:
        f.write(response.content)
    
    print(f"\n[*] Saved LLM Analysis to {analysis_filename}")
    print('\n--- RCA / Analysis Output Preview ---')
    print(response.content[:500] + "...\n[Output truncated, check markdown file for full text]")

    return response.content

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run 12-Mode RAG Pipeline for MAC Log Analysis")
    parser.add_argument('--mode', type=str, default='1', help="Mode to run: '1' through '12', or 'all'.")
    parser.add_argument('--log_file', type=str, default=DEFAULT_LOG_FILE, help="Path to the input log file.")
    parser.add_argument('--llm_model', type=str, default=DEFAULT_LLM_MODEL, help="Local LLM model name via Ollama.")
    parser.add_argument('--groq_log_file', type=str, default=DEFAULT_GROQ_LOG_FILE, help="Optional: Path to a separate log file specifically for Groq translation.")
    
    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Error: Log file '{args.log_file}' not found.")
        exit(1)

    if args.mode.lower() == 'all':
        for m in range(1, 13):
            run_pipeline(mode=m, log_filename=args.log_file, llm_model=args.llm_model, groq_log_filename=args.groq_log_file)
    else:
        try:
            selected_mode = int(args.mode)
            if selected_mode < 1 or selected_mode > 12:
                raise ValueError
            run_pipeline(mode=selected_mode, log_filename=args.log_file, llm_model=args.llm_model, groq_log_filename=args.groq_log_file)
        except ValueError:
            print("Error: Invalid mode. Please specify a number between 1 and 12, or 'all'.")
            exit(1)