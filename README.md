# 5GMACLogAnalysis

## 1. Project Overview

This project is motivated by the paper:

*LLM-5GMAC: Performance Optimization in O-RAN Split 7.2 Using LLM-Based MAC-Layer Log Analysis*, 
OpenRan '25: Proceedings of the 2nd ACM Workshop on Open and AI RAN
([https://dl.acm.org/doi/10.1145/3737900.3770164](url))

The authors provide 5G MAC logs to an LLM for root cause analysis. The key finding is that of prompt dependency. General prompts yield generic, unrelated insights into system behaviour from the logs. However, targeted prompts leverage the LLM's intelligence to build a proper, complete causal chain capturing multi-layer dependencies and provide a complete RCA.

The findings of the paper have been replicated in the chats linked below:

Link to chats with LLM

1. du_mac_logs_3.txt (Targeted Prompting): https://chatgpt.com/share/69e9ff44-8624-8322-b86b-be9ca1568db4
2. du_mac_logs_3.txt (General Prompting): https://chatgpt.com/share/69e9ff5b-2be4-8322-b3b7-a5db6c4660e0
3. harq_exhaustion_logs_new.txt (Targeted Prompting): https://chatgpt.com/share/69e9fe96-c050-8320-9e1c-4cceb04fdc96
4. harq_exhaustion_logs_new.txt (General Prompting): https://chatgpt.com/share/69e9ff0e-e1fc-8323-b38e-d3d36e413f2e

### What this project is about:

Building the targeted prompt requires operator expertise. It involves looking for a **key event** (invalid TA offset, invalid CQI error, HARQ NACKs, etc.), providing it in the prompt and asking the LLM to trace the impact of this event through the logs. This build a clean causal chain as can be seen in the chats linked above.

We attempt two things:

1. Implement RAG using 3GPP TS 38.321 and OAI mac-usage.md documentation to mitigate prompt dependency.
2. Use NLP methods and LLM's to extract key events from logs and give them to the LLM to obtain RCA.

Approach 2 performs better according to our results. 

## 2. Setup Instructions / How to run

1. Create a virtual environment and install dependencies using `pip` from `requirements.txt`
2. Copy the file `mac-usage.md` from directory `rag_docs/` to the directory `rag_docs_md/`
3. Run command `python3 scripts/convert_to_markdown_docling.py` to convert the TS 38.321 pdf to markdown.
4. Run command `python3 scripts/ingestion_pipeline.py` to perform chunking, embedding and storing embeddings vectors in chromaDB. A new directory `db/` will be created containing the database.
5. Run the commands below to generate artifacts/results of all methods implemented (13 in total) on the two main log files used for the experiments `du_mac_logs_3.txt` and `harq_exhaustion_logs_new_trimmed.txt`:
```
export GROQ_API_KEY=<your-groq-api-key-free-tier-works>

python3 scripts/full_pipeline.py --mode all --log_file log_files/du_mac_logs_3.txt --groq_log_file log_files/du_mac_logs_3_trimmed.txt

python3 scripts/full_pipeline.py --mode all --log_file log_files/harq_exhaustion_logs_new_trimmed.txt --groq_log_file log_files/harq_exhaustion_logs_new_trimmed.txt

python3 scripts/mode13_pipeline.py --log_file log_files/du_mac_logs_3.txt --groq_log_file log_files/du_mac_logs_3_trimmed.txt

python3 scripts/mode13_pipeline.py --log_file log_files/harq_exhaustion_logs_new_trimmed.txt --groq_log_file log_files/harq_exhaustion_logs_new_trimmed.txt
```

6. Results will be stored in the `results/` directory. 

`results/<log_filename>/<mode_num>/` contains the artifacts from running the method (or mode) `<mode_num>` on log file `<log_filename>`. The different modes are explained below:

## Pipeline Execution Modes

The pipeline supports **13 distinct modes** of operation. These modes allow you to test and evaluate various combinations of log event extraction techniques, Retrieval-Augmented Generation (RAG) strategies, and LLM prompt structures to find the best configuration for Root Cause Analysis (RCA).

### Core Pipeline Strategies

The modes are built by mixing and matching the following three strategies:

**1. Prompt Type**
* **Baseline:** General wireless link quality analysis. The LLM is given the raw logs and asked to assess the situation without any extracted events guiding it.
* **RCA (Root Cause Analysis):** The LLM is explicitly provided with the top 5 extracted anomalous events and asked to trace causal chains and identify the root cause.

**2. RAG Strategy (Context Retrieval)**
* **None (`wo_rag`):** No external context is retrieved. The LLM relies entirely on its internal knowledge base.
* **Concat (`with_rag_concat`):** Builds a RAG search query by concatenating the extracted log templates directly.
* **LLM Translated (`with_rag_llm`):** Uses the Groq API to translate the raw MAC logs into a plain English semantic search query, which is then used to query the vector database.

**3. Event Extraction Technique**
* **None:** No event extraction is performed (Baseline modes).
* **Static Miner:** Uses pre-defined heuristic log parsing and Drain3 to extract and score anomalies.
* **Dynamic Miner:** Uses Groq and Chi-Square statistical analysis for intelligent, dynamic template classification.
* **Clustering:** Generates sentence embeddings (via Ollama) and groups logs using Agglomerative Clustering to isolate rare events. Generates interactive t-SNE HTML visualizations.
* **Native Groq:** Directly prompts the Groq API to read the logs and extract the top 5 events natively.

---

### Mode Configuration Matrix

| Mode | Event Extraction Strategy | RAG Strategy | Prompt Type |
| :--- | :--- | :--- | :--- |
| **1** | None | None | Baseline |
| **2** | Static Miner *(For RAG query only)* | Concat | Baseline |
| **3** | None | LLM Translated | Baseline |
| **4** | Static Miner | None | RCA |
| **5** | Static Miner | Concat | RCA |
| **6** | Static Miner | LLM Translated | RCA |
| **7** | Dynamic Miner | None | RCA |
| **8** | Dynamic Miner | Concat | RCA |
| **9** | Dynamic Miner | LLM Translated | RCA |
| **10** | Embedding / Clustering | None | RCA |
| **11** | Embedding / Clustering | Concat | RCA |
| **12** | Embedding / Clustering | LLM Translated | RCA |
| **13** | Native Groq API | None | RCA |

---

### Artifact Organization

To prevent cross-contamination and keep analysis clean, all pipeline outputs are highly structured and saved dynamically based on the log file name and execution mode:

* **Mode-Specific Artifacts:** Saved to `results/<log_filename>/mode<num>/` (e.g., `results/du_mac_logs_3/mode7/`). This includes the final LLM Markdown analysis, retrieved RAG chunks, key event text files, and t-SNE visualizations.
* **Shared Cache:** To optimize API credit usage, cross-mode resources (like the Groq-translated RAG queries and Dynamic Miner JSON classifications) are saved to the parent `results/<log_filename>/` directory so they can be reused across different modes.

## 3. Results Summary

Key observations:

1. Generic prompt does not reveal causal chain, even with RAG (both forms concat+LLM translation)

2. LLM translated retrieval query built directly from logs is either incorrect (`results/du_mac_logs_3/shared_translated_query.txt`) or nonsensical (`results/harq_exhaustion_logs_new_trimmed/shared_translated_query.txt`).

3. LLM extracted top key events are often inaccuurate (`results/harq_exhaustion_logs_new_trimmed/mode13/mode13_key_events_wo_rag.txt`)

4. A targeted prompt built using extracted key events performs much better than RAG in doing RCA.

5. Classical NLP (scoring using hardcoded vocabulary, scoring using vocabulary learned from Chi2) based methods and sentence embedding based methods are better at extracting key events from the logs.  

6. RAG provides almost no improvement to key event extraction based methods.

7. Instead of RAG, it would be far better to improve key event extraction. Look into developing specialized LLM agents for key event extraction from logs (as existing LLMs are bad at this task, see point 2 above). Use this to enrich the prompt to obtain a good analysis.

## 4. LLM usage disclosure

Used LLMs to integrate individual scripts into a clean pipeline utilizing config files for setting parameters, implementing caching to save API credits, and building new scripts by extending the code in prior scripts.

After writing the rough scripts that would save directly in the working directory, would use hardcoded paths, etc. used Gemini to couple all those scripts in a single workflow utilizing `config.json` for setting paths, and model names and saving the outputs cleanly into the `results/` directory.
