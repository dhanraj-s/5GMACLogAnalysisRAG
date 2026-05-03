import os
import json
import re
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from groq import Groq
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_selection import chi2

# Ensure your GROQ_API_KEY is set in your environment variables
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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

def classify_templates_with_groq(unique_templates, output_file="template_classifications.json"):
    """Uses Groq to classify templates, loading cached results to save API calls."""
    classification_dict = {}
    
    # 1. Load existing cache if available
    if os.path.exists(output_file):
        print(f"[*] Found {output_file}. Loading cached classifications...")
        with open(output_file, 'r') as f:
            classification_dict = json.load(f)
            
    # 2. Identify missing templates that are NOT in the cache
    templates_to_classify = [t for t in unique_templates if t not in classification_dict and t != "UNMATCHED"]
    
    # 3. If everything is cached, return early without calling the API
    if not templates_to_classify:
        print("[*] All templates are already classified in the cache. Skipping API call.")
        return classification_dict
        
    # 4. Otherwise, call the API ONLY for the missing templates
    print(f"[*] Sending {len(templates_to_classify)} NEW templates to Groq for classification...")
    
    indexed_templates = [{"id": i, "template": t} for i, t in enumerate(templates_to_classify)]
    
    # prompt = (
    #     "You are an expert 5G telecom engineer. Classify the following 5G MAC log templates "
    #     "as 'NORMAL' or 'ANOMALOUS'. Return ONLY a JSON object with a single key 'results' "
    #     "containing a list of objects. Each object must have the 'id' and a 'label' "
    #     "(strictly 'NORMAL' or 'ANOMALOUS').\n\n"
    #     f"Templates: {json.dumps(indexed_templates)}"
    # )

    prompt = (
        "You are an expert 5G telecom engineer specializing in MAC layer diagnostics. "
        "Your task is to classify 5G MAC log templates as either 'NORMAL' or 'ANOMALOUS'.\n\n"
        
        "CONTEXT:\n"
        "These logs have been parsed by Drain3. Tokens like `<*>`, `<NUM>`, `<HEX>`, "
        "or `<IP>` represent masked dynamic variables. Ignore the masking and focus on the core text.\n\n"
        
        "CLASSIFICATION RULES:\n"
        "- NORMAL: Routine operations, expected state transitions, periodic reporting (e.g., CQI, MCS updates), "
        "successful allocations, heartbeat checks, and graceful teardowns/disconnects.\n"
        "- ANOMALOUS: Resource allocation failures, out-of-memory errors, unexpected drops, "
        "radio link failures (RLF), synchronization loss, invalid parameters, timeouts, and forced aborts.\n"
        "- DEFAULT: If a log is purely informational or ambiguous, classify it as NORMAL.\n\n"
        
        "EXAMPLES:\n"
        "- 'UE <NUM> connected successfully' -> NORMAL\n"
        "- 'Detected UL Failure on PUSCH after <*> DTX' -> ANOMALOUS\n"
        "- 'Routine buffer status report received' -> NORMAL\n"
        "- 'CQI <CQI_INVALID> reported for UE <*>' -> ANOMALOUS\n\n"
        
        "OUTPUT FORMAT:\n"
        "Return ONLY a valid JSON object with a single key 'results' containing a list of objects. "
        "Each object must have the 'id' (integer) and 'label' (strictly 'NORMAL' or 'ANOMALOUS').\n\n"
        
        f"Templates to classify:\n{json.dumps(indexed_templates)}"
    )
    
    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    
    response_dict = json.loads(completion.choices[0].message.content)
    
    # 5. Merge new results into the dictionary
    for item in response_dict.get('results', []):
        t_id = item['id']
        classification_dict[templates_to_classify[t_id]] = item['label'].upper()
        
    # 6. Save the updated dictionary back to the file
    print(f"[*] Updating cache file at {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(classification_dict, f, indent=4)
        
    return classification_dict

def learn_significant_stems(classification_dict):
    """Uses Chi-Square to find terms highly associated with ANOMALOUS logs."""
    print("[*] Calculating Chi-Square scores to extract significant stems...")
    
    templates = list(classification_dict.keys())
    labels = [1 if label == "ANOMALOUS" else 0 for label in classification_dict.values()]
    
    if sum(labels) == 0 or sum(labels) == len(labels):
        print("[!] Warning: LLM classified all logs as the same class. Falling back to empty significance list.")
        return set()

    vectorizer = CountVectorizer(ngram_range=(1, 1), stop_words='english', token_pattern=r'\b[a-z]+\b')
    X = vectorizer.fit_transform(templates)
    
    chi2_scores, _ = chi2(X, labels)
    
    phrases = vectorizer.get_feature_names_out()
    
    # scored_phrases = [(phrase, score) for phrase, score in zip(phrases, chi2_scores) if score > 0]
    # scored_phrases.sort(key=lambda x: x[1], reverse=True)
    
    # dynamic_words = [phrase for phrase, score in scored_phrases if score > 0.5]

    # Calculate how many times each word appears in ANOMALOUS vs NORMAL logs
    import numpy as np
    anomalous_counts = np.array(X[np.array(labels) == 1].sum(axis=0))[0]
    normal_counts = np.array(X[np.array(labels) == 0].sum(axis=0))[0]
    
    dynamic_words = []
    
    for idx, phrase in enumerate(phrases):
        score = chi2_scores[idx]
        # 1. Must pass the Chi-Square threshold
        # 2. Must appear MORE in Anomalous logs than in Normal logs
        if score > 0.5 and anomalous_counts[idx] > normal_counts[idx]:
            dynamic_words.append(phrase)
    
    print(f"[*] Dynamically learned significant words: {dynamic_words}")
    
    return set(dynamic_words)

def score_templates(template_freq, templates, log_lines, sig_stems, classification_map):
    """Scores templates based on rarity, significance, temporal position, and LLM classification."""
    total_lines = len(log_lines)
    first_occurrence = {}
    
    for i, template in enumerate(templates):
        if template not in first_occurrence:
            first_occurrence[template] = i

    scores = {}
    for template, count in template_freq.items():
        # Retrieve the LLM label, default to NORMAL if missing, and apply weight
        label = classification_map.get(template, "NORMAL")
        label_weight = 10.0 if label == "ANOMALOUS" else 0.01

        rarity_score = 1 - (count / total_lines)

        template_words = re.findall(r'\b[a-z]+\b', template.lower())
        #template_stems = set(token.lemma_ for token in nlp(template.lower()))

        significance_score = sum(
            1 for word in sig_stems
            if word in template_words
        )
        
        position = first_occurrence.get(template, total_lines)
        temporal_score = 1 - (position / total_lines)
        
        # Multiply everything by the label_weight
        scores[template] = rarity_score * (significance_score + 1) * label_weight #(1 + temporal_score) * label_weight

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def get_scored_events(log_filename, results_dir):
    config = TemplateMinerConfig()
    config.parametrize_numeric_tokens = True
    miner = TemplateMiner(config=config)

    with open(log_filename, 'r') as f:
        log_lines = [clean_log_line(line) for line in f.read().split('\n') if line != '']
    
    for line in log_lines:
        miner.add_log_message(line)

    templates = []
    for line in log_lines:
        result = miner.match(line)
        if result:
            templates.append(result.get_template())
        else:
            templates.append("UNMATCHED")

    template_freq = dict()
    for template in templates:
        template_freq[template] = template_freq.get(template, 0) + 1
        
    unique_templates = list(template_freq.keys())

    #base_name = os.path.splitext(os.path.basename(log_filename))[0]
    #dynamic_json_file = f"{base_name}_classifications.json"
    #dynamic_json_file = os.path.join(results_dir, "template_classifications.json")

    #dynamic_json_file = os.path.join(os.path.dirname(results_dir), "template_classifications.json")
    
    # Save cache in the parent directory so modes 7, 8, and 9 can share it!
    dynamic_json_file = os.path.join(os.path.dirname(results_dir), "template_classifications.json")
    
    # AI classification with Delta Caching
    classification_map = classify_templates_with_groq(unique_templates, output_file=dynamic_json_file)
    dynamic_sig_stems = learn_significant_stems(classification_map)
    
    #return score_templates(template_freq, templates, log_lines, dynamic_sig_stems, classification_map)
    scored = score_templates(template_freq, templates, log_lines, dynamic_sig_stems, classification_map)
    return scored, list(dynamic_sig_stems)

if __name__ == '__main__':
    scored_events = get_scored_events('log_files/harq_exhaustion_logs_new.txt')
    print("\n--- Final Scored Events ---")
    for ev in scored_events:
        print(ev)