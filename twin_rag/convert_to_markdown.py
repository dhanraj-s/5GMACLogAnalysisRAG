from markitdown import MarkItDown
import re
import os

INPUT_DIR = 'docs/'
OUTPUT_DIR = 'docs_md/'

if not os.path.exists(INPUT_DIR):
    raise FileNotFoundError(\
        f'The input directory {INPUT_DIR} containing source documents does not exist. Please create one and add your source docs.'\
    )

os.makedirs(OUTPUT_DIR, exist_ok=True)

SRC_FILES = [f for f in os.listdir(INPUT_DIR) if re.search(r'\.md$', f) is None]

md = MarkItDown()

results = [md.convert(INPUT_DIR+filename) for filename in SRC_FILES]

def fix_3gpp_headings(text):
    lines = text.split('\n')
    fixed = []
    for line in lines:
        line = line.strip()

        if re.match(r'\d+\.\d+\.\d+\.\d+\s+[A-Z]', line):
            line = f'#### {line}'
        elif re.match(r'\d+\.\d+\.\d+\s+[A-Z]', line):
            line = f'### {line}'
        elif re.match(r'\d+\.\d+\s+[A-Z]', line):
            line = f'## {line}'
        elif re.match(r'\d+\s+[A-Z]', line):
            line = f'# {line}'
        fixed.append(line)

    return '\n'.join(fixed)

def is_3gpp(filename):
    return re.match(r'ts_', filename)


for i,result in enumerate(results):
    with open(OUTPUT_DIR+SRC_FILES[i]+'.md', 'w') as f:
        if is_3gpp(SRC_FILES[i]):
            f.write(fix_3gpp_headings(result.text_content))
        else:
            f.write(result.text_content)
        