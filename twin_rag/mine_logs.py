from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
import re
from nltk.stem import PorterStemmer

def clean_log_line(line):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    line = ansi_escape.sub('', line)

    line = re.sub(r'\[NR_\w+\]', '', line)
    line = re.sub(r'\[MAC\]', '', line)
    line = re.sub(r'CQI\s+0\b', 'CQI <CQI_INVALID>', line, flags=re.IGNORECASE)
    line = re.sub(r'MCS\s+\(\d+\)\s+0\b', 'MCS <MCS_INVALID>', line, flags=re.IGNORECASE)
    line = re.sub(r'MCS\s+0\b', 'MCS <MCS_INVALID>', line, flags=re.IGNORECASE)

    line = ' '.join(line.split())

    return line.strip()

stemmer = PorterStemmer()

def score_templates(template_freq, templates, log_lines):
    total_lines = len(log_lines)

    # for temporal scoring. events appearing first are more likely to be root causes.
    first_occurrence = {}
    for i, template in enumerate(templates):
        if template not in first_occurrence:
            first_occurrence[template] = i

    SIGNIFICANT = [
        "fail", "invalid", "loss", "drop",
        "timeout", "exceed", "mismatch", "unknown",
        "abort", "reject", "release", "disconnect",
        "retx", "nack", "corrupt"
    ]

    sig_stems = set(stemmer.stem(w) for w in SIGNIFICANT)
    sig_stems.add("failure")

    scores = {}

    for template, count in template_freq.items():

        rarity_score = 1 - (count / total_lines)

        template_words = re.findall(r'\b[a-z]+\b', template.lower())
        template_stems = set(stemmer.stem(w) for w in template_words)

        significance_score = sum(
            1 for word in sig_stems
            if word in template_stems
        )
        
        position = first_occurrence.get(template, total_lines)
        temporal_score = 1 - (position/total_lines)
        scores[template] = rarity_score * (significance_score + 1) * (1 + temporal_score)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def get_scored_events(log_filename):
    config = TemplateMinerConfig()
    config.parametrize_numeric_tokens = True
    miner = TemplateMiner(config=config)
    templates = []

    with open(log_filename, 'r') as f:
        log_lines = [clean_log_line(line) for line in f.read().split('\n') if line != '']
    
    for line in log_lines:
        result = miner.add_log_message(line)

    templates = []
    for line in log_lines:
        result = miner.match(line)
        if result:
            templates.append(result.get_template())
        else:
            templates.append("UNMATCHED")

    template_freq = dict()
    for template in templates:
        template_freq[template] = template_freq.get(template,0) + 1
    
    return score_templates(template_freq, templates, log_lines)


if __name__ == '__main__':
    scored_events = get_scored_events('log_files/du_mac_logs_3.txt')
    for ev in scored_events:
        print(ev)
    


