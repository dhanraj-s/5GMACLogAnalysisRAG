import os
import sys
import json
import argparse
from groq import Groq
from langchain_ollama import ChatOllama

# --- System Path Setup ---
# Works perfectly from the 'scripts/' directory
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# --- Project Imports ---
from src.mine_logs import clean_log_line

# --- Load Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../configs/config.json')

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"Error: Configuration file not found at {CONFIG_PATH}")
    print("Please create the file according to the instructions.")
    sys.exit(1)

OLLAMA_ADDR = config.get('OLLAMA_ADDR', 'http://localhost:11434')
GROQ_MODEL = config.get('GROQ_MODEL', 'llama3.3-70b-versatile')
RESULTS_DIR = config.get('RESULTS_DIR', '../results')
DEFAULT_LOG_FILE = config.get('DEFAULT_LOG_FILE', '../log_files/du_mac_logs_3.txt')
DEFAULT_GROQ_LOG_FILE = config.get('DEFAULT_GROQ_LOG_FILE', None)
DEFAULT_LLM_MODEL = config.get('DEFAULT_LLM_MODEL', 'gemma4:latest')

# --- Helper Functions ---

def load_log(log_filename):
    with open(log_filename, 'r', encoding='utf-8') as f:
        raw = f.read()
    cleaned_lines = [
        clean_log_line(line)
        for line in raw.split('\n')
        if line.strip()
    ]
    return '\n'.join(cleaned_lines)

def extract_top5_with_groq(groq_log_segment, results_dir):
    """Uses Groq to directly read the separate Groq logs and extract the top 5 anomalies."""
    events_filename = os.path.join(results_dir, "mode13_key_events_wo_rag.txt")
    
    # Cache check to save API credits
    if os.path.exists(events_filename):
        print(f"[*] Cached Groq events found. Loading from {events_filename}...")
        with open(events_filename, 'r', encoding='utf-8') as f:
            return f.read().strip()
            
    print(f"[*] Contacting Groq API ({GROQ_MODEL}) to extract top 5 anomalies natively...")
    groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    prompt = f"""
    You are an expert telecommunications network engineer analyzing MAC layer logs.
    Your task is to identify the 5 most critical anomalous events, errors, or metric degradations in the logs below.
    
    Instructions:
    1. Output EXACTLY 5 log lines from the provided text, numbered 1 to 5.
    2. Do NOT add any conversational filler, explanations, or quotes. 
    3. Only output the numbered list.

    RAW MAC LOGS:
    {groq_log_segment}
    """
    
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    
    top5_str = response.choices[0].message.content.strip()
    
    with open(events_filename, 'w', encoding='utf-8') as f:
        f.write(top5_str)
    print(f"[*] Saved extracted key events to {events_filename}")
    
    return top5_str

def build_prompt(top5_str, log_segment):
    """Builds the final prompt without RAG, using the main log segment."""
    return f"""     
    MAC LAYER LOGS:
    {log_segment}

    FIVE ANOMALOUS EVENTS DETECTED:
    {top5_str}

    Find the root cause event from the five events listed above. Analyze the root cause event error and trace its impact on subsequent connection quality. Build a causal chain.
    """

# --- Main Execution Pipeline ---

def run_mode13(log_filename, llm_model, groq_log_filename=None):
    print(f'\n{"="*50}')
    print(f'--- Initializing Pipeline in MODE 13 using {llm_model} ---')
    print(f'{"="*50}')
    
    # --- Setup Results Directory Structure ---
    base_log_name = os.path.basename(log_filename)
    clean_log_name = os.path.splitext(base_log_name)[0]
    
    # Path: ../results/<clean_log_name>/mode13/
    base_results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), RESULTS_DIR, clean_log_name)
    results_dir = os.path.join(base_results_dir, "mode13")
    os.makedirs(results_dir, exist_ok=True)
    
    print(f"[*] Artifacts will be saved to: {results_dir}")
    print(f'Loading main logs from {log_filename}...')
    log_segment = load_log(log_filename)
    
    # Load the separate log for Groq if provided, otherwise fallback to the main log
    if groq_log_filename and os.path.exists(groq_log_filename):
        print(f'[*] Loading separate Groq extraction logs from {groq_log_filename}...')
        groq_log_segment = load_log(groq_log_filename)
    else:
        groq_log_segment = log_segment
    
    # Step 1: Extract events natively via Groq using the specific Groq logs
    top5_str = extract_top5_with_groq(groq_log_segment, results_dir)
    print(f'\nTop 5 events extracted by Groq:\n{top5_str}\n')
    
    # Step 2: Build final prompt (No RAG) using the main logs
    prompt = build_prompt(top5_str, log_segment)

    # Step 3: Execute Final LLM RCA Request
    print(f'\nInitializing local LLM ({llm_model})...')
    llm = ChatOllama(
        model=llm_model,
        base_url=OLLAMA_ADDR,
        temperature=0,
    )
    
    print(f'\nExecuting final RCA LLM inference via {llm_model}...')
    response = llm.invoke(prompt)
    
    analysis_filename = os.path.join(results_dir, "mode13_analysis_wo_rag.md")
    with open(analysis_filename, 'w', encoding='utf-8') as f:
        f.write(response.content)
    
    print(f"\n[*] Saved LLM Analysis to {analysis_filename}")
    print('\n--- RCA / Analysis Output Preview ---')
    print(response.content[:500] + "...\n[Output truncated, check markdown file for full text]")

    return response.content

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run Mode 13 (Native Groq Extraction, No RAG) for MAC Log Analysis")
    parser.add_argument('--log_file', type=str, default=DEFAULT_LOG_FILE, help="Path to the input log file.")
    parser.add_argument('--groq_log_file', type=str, default=DEFAULT_GROQ_LOG_FILE, help="Optional: Path to a separate log file specifically for Groq extraction.")
    parser.add_argument('--llm_model', type=str, default=DEFAULT_LLM_MODEL, help="Local LLM model name via Ollama.")
    
    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"Error: Log file '{args.log_file}' not found.")
        sys.exit(1)

    run_mode13(log_filename=args.log_file, llm_model=args.llm_model, groq_log_filename=args.groq_log_file)