import os
import re
import json
from fitz import open as open_pdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

class DocumentProcessor:
    def __init__(self, docs_path="./data/documents", registry_path="./data/ingestion_registry.json"):
        self.docs_path = docs_path
        self.registry_path = registry_path
        # REQ-02: 500-char chunks with 50-char overlap
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    def _load_registry(self):
        """Loads previous ingestion state."""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_registry(self, registry):
        """Saves current state to file."""
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        with open(self.registry_path, 'w') as f:
            json.dump(registry, f, indent=4)

    def clean_pii(self, text):
        """M-10/REQ-10: Redacts sensitive PII from text before embedding generation."""
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', text)
        text = re.sub(r'\b(?:\+91|0)?[6-9]\d{9}\b', '[REDACTED_PHONE]', text)
        text = re.sub(r'\b\d{4}[\s-]\d{4}[\s-]\d{4}\b', '[REDACTED_AADHAAR]', text)
        text = re.sub(r'\b[A-Z]{5}\d{4}[A-Z]{1}\b', '[REDACTED_PAN]', text)
        return text

    def extract_and_chunk(self):
        """Extracts text ONLY from new or modified PDFs, masks PII, and updates the registry."""
        all_chunks = []
        if not os.path.exists(self.docs_path) or len(os.listdir(self.docs_path)) == 0:
            return all_chunks

        registry = self._load_registry()
        new_registry = dict(registry)
        files_to_process = []
        any_processed = False

        # Filter documents based on modified time
        for file_name in os.listdir(self.docs_path):
            if file_name.endswith('.pdf'):
                file_path = os.path.join(self.docs_path, file_name)
                mtime = os.path.getmtime(file_path)
                
                # Process only if file is new or modified
                if file_name not in registry or registry[file_name] != mtime:
                    files_to_process.append((file_name, file_path, mtime))

        for file_name, file_path, mtime in files_to_process:
            try:
                with open_pdf(file_path) as doc:
                    for page_num in range(len(doc)):
                        page_text = doc[page_num].get_text()
                        if not page_text.strip(): 
                            continue # Skip empty pages
                        
                        # Apply your custom clean_pii pattern matcher before chunking
                        masked_text = self.clean_pii(page_text)
                        
                        metadata = {"source": file_name, "page": page_num + 1}
                        chunks = self.splitter.split_text(masked_text)
                        
                        for chunk in chunks:
                            all_chunks.append({"text": chunk, "metadata": metadata})
                
                # Mark as successfully processed
                new_registry[file_name] = mtime
                any_processed = True
            except Exception as e:
                print(f"Failed to process file {file_name}: {e}")
                
        # Automatically commit state changes if new files were processed
        if any_processed:
            self._save_registry(new_registry)
                            
        return all_chunks