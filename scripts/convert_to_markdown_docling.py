import os
import sys
import json
import re
import html
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions

# --- Load Configuration ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../configs/config.json')

try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"[!] Error: Configuration file not found at {CONFIG_PATH}")
    print("[!] Please create the configuration file before running.")
    sys.exit(1)

# Resolve input and output directories relative to this script's location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR_RAW = config.get('DOCS_INPUT_DIR', '../rag_docs')
OUTPUT_DIR_RAW = config.get('DOCS_OUTPUT_DIR', '../rag_docs_md')

INPUT_DIR = os.path.normpath(os.path.join(BASE_DIR, INPUT_DIR_RAW))
OUTPUT_DIR = os.path.normpath(os.path.join(BASE_DIR, OUTPUT_DIR_RAW))

# --- Directory Checks ---
if not os.path.exists(INPUT_DIR):
    print(f"\n[!] Error: The input directory '{INPUT_DIR}' does not exist.")
    print("[!] Please create it and add your source PDFs before running the converter.\n")
    sys.exit(1)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Processing Files ---
SRC_FILES = [f for f in os.listdir(INPUT_DIR) if re.search(r'\.md$', f) is None]

if not SRC_FILES:
    print(f"\n[*] No non-markdown documents found in '{INPUT_DIR}'. Exiting.\n")
    sys.exit(0)

print(f"[*] Found {len(SRC_FILES)} files to convert in {INPUT_DIR}.")
print("[*] Initializing Docling DocumentConverter...")
converter = DocumentConverter()

results = []
for src in SRC_FILES:
    file_path = os.path.join(INPUT_DIR, src)
    print(f"[*] Converting: {src}")
    results.append(converter.convert(file_path))

def fix_3gpp_heading(text):
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        if line.startswith('##'):
            line = line.strip()
            heading = ' '.join(line.split(' ')[1:])
            
            if re.match(r'\d+\.\d+\.\d+\.\d+\.\d+\.\d+', heading):
                line = '###### ' + heading
            elif re.match(r'\d+\.\d+\.\d+\.\d+\.\d+', heading):
                line = '##### ' + heading
            elif re.match(r'\d+\.\d+\.\d+\.\d+', heading):
                line = '#### ' + heading
            elif re.match(r'\d+\.\d+\.\d+', heading):
                line = '### ' + heading
            
        fixed_lines.append(line)
    return '\n'.join(fixed_lines)

print(f"[*] Post-processing headings and saving to {OUTPUT_DIR}...")
for i, result in enumerate(results):
    out_filename = f"{SRC_FILES[i]}.md"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(fix_3gpp_heading(html.unescape(result.document.export_to_markdown(strict_text=True))))
    print(f"[*] Saved: {out_filename}")

print("[*] Conversion complete!")