import os
import time
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

# Import CrossEncoder from sentence-transformers (already in your env)
from sentence_transformers import CrossEncoder

class VectorDatabase:
    def __init__(self, db_path="./chroma_db"):
        self.db_path = db_path
        
        # DECLARE IMMEDIATELY: Prevents attribute errors during startup
        self.vector_db = None
        self.bm25_retriever = None
        
        # REQ-02: Initializing the bge-base-en-v1.5 model (768 dimensions)
        self.embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en-v1.5")
        
        # NEW: Load local lightweight Cross-Encoder (~270MB model)
        # It automatically downloads on the first run, then operates 100% offline
        self.reranker = CrossEncoder("BAAI/bge-reranker-base")
        
        self._load_db()

    def _load_db(self):
        """Loads database connections and caches both Chroma and BM25 search indexes in memory."""
        if os.path.exists(self.db_path) and os.listdir(self.db_path):
            self.vector_db = Chroma(
                persist_directory=self.db_path, 
                embedding_function=self.embedding_model
            )
            
            # Extract stored documents to construct and cache the BM25 index
            stored_data = self.vector_db.get()
            if stored_data and stored_data.get("documents"):
                doc_list = []
                for text, meta in zip(stored_data["documents"], stored_data["metadatas"]):
                    doc_list.append(Document(page_content=text, metadata=meta))
                
                # Cache the BM25 retriever instance
                self.bm25_retriever = BM25Retriever.from_documents(doc_list)
            else:
                self.bm25_retriever = None
        else:
            self.vector_db = None
            self.bm25_retriever = None

    def save_chunks_to_db(self, chunks):
        """Appends new chunks to the database and automatically updates the cached indexes."""
        if not chunks:
            return 0
        
        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        if self.vector_db is None:
            self.vector_db = Chroma.from_texts(
                texts=texts,
                embedding=self.embedding_model,
                metadatas=metadatas,
                persist_directory=self.db_path
            )
        else:
            self.vector_db.add_texts(texts=texts, metadatas=metadatas)
        
        # Refresh the cached database and BM25 index on the fly
        self._load_db()
        return len(chunks)

    def retrieve_context_hybrid(self, query, top_k=3):
        """Retrieves matching chunks utilizing a manual Reciprocal Rank Fusion (BM25 + Semantic)
        and refines the ranking using a Cross-Encoder Reranker.
        """
        if self.vector_db is None:
            self._load_db()
            if self.vector_db is None:
                return [], 0.0, 9.9

        start_time = time.time()
        
        # Stage 1: Gather a slightly larger pool of candidates (e.g., top_k * 3) for the reranker
        candidate_count = top_k * 3
        vector_results = self.vector_db.similarity_search_with_score(query, k=candidate_count)
        
        # Capture the absolute closest distance for our security threshold in app.py
        absolute_best_distance = vector_results[0][1] if vector_results else 9.9
        vector_docs = [res[0] for res in vector_results]

        # Fetch candidates from BM25
        bm25_docs = []
        if self.bm25_retriever is not None:
            self.bm25_retriever.k = candidate_count
            bm25_docs = self.bm25_retriever.invoke(query)
            
        # Apply Reciprocal Rank Fusion (RRF) to merge duplicates and compile candidates
        c = 60
        rrf_scores = {}
        doc_map = {}      
        
        for rank, (doc, score) in enumerate(vector_results, 1):
            content = doc.page_content
            doc_map[content] = doc
            rrf_scores[content] = rrf_scores.get(content, 0) + 1.0 / (60 + rank)
            
        for rank, doc in enumerate(bm25_docs, 1):
            content = doc.page_content
            doc_map[content] = doc
            rrf_scores[content] = rrf_scores.get(content, 0) + 1.0 / (60 + rank)
            
        sorted_contents = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        
        # Compile the top candidate pool (e.g., top 10 unique documents)
        candidate_pool = [doc_map[content] for content in sorted_contents[:candidate_count]]
        
        # ==========================================
        # STAGE 2: CROSS-ENCODER RERANKING
        # ==========================================
        fused_docs_with_scores = []
        
        if candidate_pool and self.reranker is not None:
            # Pair each candidate text with the user query
            pairs = [[query, doc.page_content] for doc in candidate_pool]
            
            # Predict similarity scores (higher is more relevant)
            rerank_scores = self.reranker.predict(pairs)
            
            # Map candidate documents to their new cross-encoder scores
            reranked_docs = []
            for doc, score in zip(candidate_pool, rerank_scores):
                reranked_docs.append((doc, float(score)))
                
            # Sort strictly by the cross-encoder's score (descending)
            reranked_docs.sort(key=lambda x: x[1], reverse=True)
            
            # Take the top_k best documents
            fused_docs_with_scores = reranked_docs[:top_k]
        else:
            # Fallback if no candidates are found or if the reranker fails
            for content in sorted_contents[:top_k]:
                fused_docs_with_scores.append((doc_map[content], 0.80))
                
        latency = time.time() - start_time
        
        return fused_docs_with_scores, latency, absolute_best_distance
