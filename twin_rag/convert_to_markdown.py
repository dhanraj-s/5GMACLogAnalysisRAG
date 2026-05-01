from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, AcceleratorOptions
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


for i,result in enumerate(results):
    with open(OUTPUT_DIR+SRC_FILES[i]+'.md', 'w') as f:
        f.write(fix_3gpp_heading(html.unescape(result.document.export_to_markdown(strict_text=True))))
