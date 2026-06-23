# 📂 Grounded Corporate Knowledge Portal (v4.0)
### 100% Offline RAG-Based Company Policy Q&A System



## 🔍 Project Overview
This application is an internal-use, fully air-gapped conversational web application designed to ingest corporate policy documents (PDF manuals) and provide employees with a conversational chatbot interface to ask natural language questions [5]. 

The system utilizes an advanced, multi-stage **Retrieval-Augmented Generation (RAG)** pipeline optimized to run strictly on local hardware, maintaining absolute corporate data sovereignty and completely preventing LLM hallucinations [5, 12].

---

## 🚀 Key Technical Features (SRS v4.0 Compliance)

### 1. 100% Local & Air-Gapped Data Sovereignty (REQ-07)
The system operates entirely offline [12]. No external cloud APIs (such as OpenAI or Firebase) are used [1.1.2]. Natural language generation (Llama 3.2 via Ollama), embedding translation (BGE-Small), and vector storage (ChromaDB) run 100% locally on your machine [7, 10, 11].

### 2. Hybrid Lexical & Dense Search (REQ-03 / M3)
To overcome the limitations of dense-only search on specific acronyms and clause numbers, the retriever combines [14]:
*   **Dense Semantic Search:** Powered by `BAAI/bge-small-en-v1.5` embeddings [7, 10].
*   **Lexical Keyword Search:** Powered by the BM25 algorithm [14].
*   **Reciprocal Rank Fusion (RRF):** Fuses both dense and lexical results using custom RRF mathematical ranking to ensure maximum precision [14].

### 3. Automated PII Redaction Pipeline (REQ-10 / M10)
During ingestion, text is scrubbed of sensitive Personal Identifiable Information (PII) before it is vectorized or stored [10]. High-speed regular expressions automatically sanitize [10]:
*   Corporate & personal email addresses
*   Indian mobile phone numbers
*   Aadhaar card numbers (UIDAI)
*   Permanent Account Numbers (PAN cards)

### 4. Zero-Hallucination Relevance Thresholding (REQ-05 / M5)
The system runs the local LLM at a strict `0.0` temperature [8, 10]. If the best-retrieved document chunk has a similarity distance score $> 1.15$ (indicating no relevant match exists in the database), the code immediately intercepts the pipeline, bypasses the LLM, and outputs exactly: `"I do not know."` [10, 14]

### 5. Conversational Query Rewriting (REQ-07 / M7)
To support multi-turn scrolling dialogue (resolving follow-up pronouns like "it", "they", or "she"), the local Llama 3.2 model acts as a query condenser [10, 14]. It analyzes the 3-turn chat history and rewrites follow-up questions into standalone queries before searching the index [10, 14].

### 6. Cryptographic Local Gateway Gatekeeper (REQ-07 / M8)
Replaces unsecure shared passcodes with a secure, offline **Admin Passcode Gate** [1.1.2, 1.1.6]. User credentials are saved locally inside `config/users.json` [1.1.2]. Passwords are encrypted using **SHA-256 one-way cryptographic hashing** [7.3, 1.1.2]. Self-registration is protected by an offline **Corporate Invitation Token** [1.1.2].

## 📂 Directory Structure
```text
rag-policy-system/
│
├── .streamlit/
│   └── config.toml             # Forces light theme settings globally
│
├── config/
│   └── users.json              # SHA-256 Hashed Offline User DB (Auto-generated)
│
├── data/
│   └── documents/              # Place raw policy PDFs here for ingestion
│
├── chroma_db/                  # Local SQLite-backed vector storage (Auto-generated)
│
├── modules/
│   ├── __init__.py             # Empty initialization file
│   ├── ingestion.py            # PDF text parsing & PII Scrubbing (Req-10)
│   ├── database.py             # BGE Embeddings, BM25, & RRF Fusion (Req-01/03)
│   └── generation.py           # Strict Qwen/Llama inference & Query Rewriter (Req-04/07)
│
├── app.py                      # Streamlit UI & Route controller
├── requirements.txt            # Local Python dependencies
├── .gitignore                  # Keeps local files out of Git tracking
├── admin_secure.log            # Append-only security audit log (Req-08)
└── README.md                   # Setup and execution guide
