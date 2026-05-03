from sklearn.ensemble import IsolationForest
from langchain_ollama import OllamaEmbeddings
from sklearn.manifold import TSNE
from sklearn.cluster import AgglomerativeClustering
import plotly.express as px
import numpy as np
import collections

# --- Configuration ---
LOG_FILE_NAME = 'log_files/du_mac_logs_3.txt'
EMBEDDING_MODEL = 'qwen3-embedding:4b'
OLLAMA_ADDR = 'http://localhost:11434'

# --- Initialization ---
embedding_model = OllamaEmbeddings(
    model = EMBEDDING_MODEL,
    base_url = OLLAMA_ADDR
)

def analyze_single_log_file(text: str, num_clusters=15):
    # 1. Clean and parse log lines
    log_lines = text.split('\n')
    log_lines = [log_line.strip() for log_line in log_lines if log_line != '']

    # 2. Generate sentence embeddings
    print("[*] Generating sentence embeddings via Ollama...")
    vectors = embedding_model.embed_documents(log_lines)
    X = np.array(vectors)

    # 3. Cluster the embeddings
    print(f"[*] Grouping logs into {num_clusters} clusters...")
    clusterer = AgglomerativeClustering(n_clusters=num_clusters, linkage='ward')
    cluster_labels = clusterer.fit_predict(X)

    # 4. Anomaly extraction based on cluster size (Majority Voting)
    print("[*] Identifying smallest clusters as anomalies...")
    cluster_counts = collections.Counter(cluster_labels)

    # Sort clusters by size (ascending)
    sorted_clusters = sorted(cluster_counts.items(), key=lambda x: x[1])

    print(f"\n--- All {len(sorted_clusters)} Clusters (Smallest to Largest) ---")
    for cluster_id, size in sorted_clusters:
        
        # Collect every single log line that belongs to this specific cluster
        logs_in_cluster = [
            log_lines[i] for i, label in enumerate(cluster_labels) 
            if label == cluster_id
        ]
        
        # Count the exact string occurrences and grab the most common one
        majority_log = collections.Counter(logs_in_cluster).most_common(1)[0][0]
        
        print(f"Cluster {cluster_id:2} | Size: {size:<4} | Majority Log: {majority_log}")
    print("-----------------------------------------------------------\n")

    # Get the top 5 smallest clusters
    top_5_smallest = sorted_clusters[:5]

    print("\n--- Top 5 Anomalous Events (Based on Smallest Clusters) ---")
    for rank, (cluster_id, size) in enumerate(top_5_smallest, start=1):
        
        # Collect every single log line that belongs to this specific cluster
        logs_in_cluster = [
            log_lines[i] for i, label in enumerate(cluster_labels) 
            if label == cluster_id
        ]
        
        # Count the exact string occurrences and grab the most common one
        majority_log = collections.Counter(logs_in_cluster).most_common(1)[0][0]
        
        print(f"{rank}. Cluster {cluster_id} (Size: {size}) -> {majority_log}")
    print("-----------------------------------------------------------\n")

    # 5. Dimensionality Reduction for Visualization
    print('[*] Running t-SNE dimensionality reduction...')
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    tsne_results = tsne.fit_transform(X)

    plot_data = {
        'X_Coordinate': tsne_results[:, 0],
        'Y_Coordinate': tsne_results[:, 1],
        'Log_Text': log_lines,
        'Line_Number': [i+1 for i in range(len(log_lines))],
        "Cluster": [f"Cluster {label}" for label in cluster_labels]
    }

    # 6. Generate and save the Plotly HTML graph
    print('[*] Generating plot.')
    fig = px.scatter(
        plot_data,
        x='X_Coordinate',
        y='Y_Coordinate',
        color="Cluster",
        hover_data={'Log_Text': True, 'Line_Number': True, 'X_Coordinate': False, 'Y_Coordinate': False},
        title='t-SNE visualization of MAC log vectors'
    )

    fig.update_traces(marker=dict(size=5, opacity=0.7))

    output_file = "tsne_mac_logs.html"
    fig.write_html(output_file)
    print(f"[*] Success! Interactive plot saved to {output_file}")

# --- Execution ---
if __name__ == '__main__':
    try:
        with open(LOG_FILE_NAME, 'r', encoding='utf-8') as f:
            log_text = f.read()
            analyze_single_log_file(log_text)
    except FileNotFoundError:
        print(f"[!] Error: Could not find the file at {LOG_FILE_NAME}. Please check the path.")