import os
import sys
import pandas as pd
import logging
from datasets import Dataset

# Setup logging to track progress
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import your custom RAG modules
from modules.database import VectorDatabase
from modules.generation import LLMGenerator

# Import Ragas and LangChain evaluation components
from ragas import evaluate
from ragas.metrics import context_recall, faithfulness
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

# Handle Ragas version compatibility for Langchain wrappers
try:
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    USE_WRAPPERS = True
except ImportError:
    USE_WRAPPERS = False

def run_benchmarking():
    logging.info("Initializing Local RAG Pipeline Components...")
    # 1. Load your RAG classes
    vector_db = VectorDatabase()
    llm_gen = LLMGenerator()
    
    # 2. Load the CSV benchmarking dataset
    csv_path = os.path.join("data", "benchmarking_data.csv")
    if not os.path.exists(csv_path):
        logging.error(f"Could not find {csv_path}. Please ensure it exists.")
        return
        
    df = pd.read_csv(csv_path)
    
    # Ragas requires these exact 4 lists
    questions = []
    ground_truths = []
    answers = []
    contexts = []

    logging.info(f"Processing {len(df)} questions through the local RAG pipeline...")
    
    # 3. Generate answers using your pipeline (simulating your app.py logic)
    for index, row in df.iterrows():
        question = row['question']
        ground_truth = row['ground_truth']
        
        logging.info(f"Processing Q{index+1}: {question[:50]}...")
        
        # Step A: Retrieve chunks via Hybrid Search
        retrieved_docs_with_scores, _ = vector_db.retrieve_context_hybrid(question, top_k=3)
        
        # Extract just the text for Ragas context evaluation
        extracted_contexts = [doc.page_content for doc, score in retrieved_docs_with_scores] if retrieved_docs_with_scores else [""]
        
        # Step B: Apply the Safety Thresholding Logic (exactly as it is in app.py)
        best_score = retrieved_docs_with_scores[0][1] if retrieved_docs_with_scores else 9.9
        
        if best_score > 1.15:
            ai_response = "I do not know."
        else:
            # Step C: Generate AI Response
            ai_response, _, _ = llm_gen.generate_response(question, retrieved_docs_with_scores)
            
        # Append to our tracking lists
        questions.append(question)
        ground_truths.append(ground_truth)
        answers.append(ai_response)
        contexts.append(extracted_contexts)
        
    # 4. Format into HuggingFace Dataset
    data_dict = {
        "question": questions,
        "ground_truth": ground_truths,
        "answer": answers,
        "contexts": contexts
    }
    dataset = Dataset.from_dict(data_dict)
    
    # 5. Initialize the Local Models for Ragas to use as "Judges"
    logging.info("Initializing Local Evaluator Models (Llama 3.2 & BGE-Small)...")
    local_llm = ChatOllama(model="llama3.2", temperature=0.0,format="json")
    local_embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5", 
        model_kwargs={"device": "cpu"}
    )
    
    # Apply wrappers if using newer Ragas versions
    if USE_WRAPPERS:
        eval_llm = LangchainLLMWrapper(local_llm)
        eval_embeddings = LangchainEmbeddingsWrapper(local_embeddings)
    else:
        eval_llm = local_llm
        eval_embeddings = local_embeddings

    # 6. Execute Ragas Evaluation
    logging.info("Starting Ragas Mathematical Evaluation...")
    logging.info("Note: Llama 3.2 acts as the Judge. This may take 20-30 minutes locally.")
    
    result = evaluate(
        dataset=dataset,
        metrics=[context_recall, faithfulness],
        llm=eval_llm,
        embeddings=eval_embeddings,
        raise_exceptions=False # Crucial: Prevents the script from crashing if a small model fails to output strict JSON
        max_workers=1
    )
    
    # 7. Export results
    logging.info("Evaluation Complete! Exporting to CSV...")
    result_df = result.to_pandas()
    result_df.to_csv("ragas_evaluation_results.csv", index=False)
    
    print("\n" + "="*40)
    print("FINAL BENCHMARK SCORES")
    print("="*40)
    print(result)
    print(f"\nDetailed per-question breakdown saved to: ragas_evaluation_results.csv")

if __name__ == "__main__":
    run_benchmarking()