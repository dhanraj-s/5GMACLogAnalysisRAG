from docling.document_converter import DocumentConverter
import os, re, html

INPUT_DIR = 'docs/'
OUTPUT_DIR = 'docs_md/'

if not os.path.exists(INPUT_DIR):
    raise FileNotFoundError(\
        f'The input directory {INPUT_DIR} containing source documents does not exist. Please create one and add your source docs.'\
    )

os.makedirs(OUTPUT_DIR, exist_ok=True)

SRC_FILES = [f for f in os.listdir(INPUT_DIR) if re.search(r'\.md$', f) is None]


converter = DocumentConverter()
results = [converter.convert(INPUT_DIR+src) for src in SRC_FILES]

for i,result in enumerate(results):
    with open(OUTPUT_DIR+SRC_FILES[i]+'.md', 'w') as f:
        f.write(html.unescape(result.document.export_to_markdown(strict_text=True)))
