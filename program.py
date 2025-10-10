#hello

import os
import google.generativeai as genai
from PyPDF2 import PdfReader
from docx import Document
import re
from dotenv import load_dotenv

load_dotenv()

class GeminiDocumentQA:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
        
        genai.configure(api_key=self.api_key)
        
        # Use a model with large context window
        self.model = genai.GenerativeModel('models/gemini-2.0-flash')
        self.document_text = ""
        self.loaded_files = []  # Track loaded files
        self.folder_path = None  # Track the uploaded folder
    
    def load_document(self, file_path):
        """Load a single document from various formats"""
        file_extension = file_path.lower().split('.')[-1]
        
        try:
            if file_extension == 'pdf':
                text = self._load_pdf(file_path)
            elif file_extension == 'docx':
                text = self._load_docx(file_path)
            elif file_extension in ['txt', 'md']:
                text = self._load_text(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            # Append to existing document text
            if self.document_text:
                self.document_text += f"\n\n--- Document: {os.path.basename(file_path)} ---\n\n{text}"
            else:
                self.document_text = f"--- Document: {os.path.basename(file_path)} ---\n\n{text}"
            
            self.loaded_files.append(file_path)
            print(f"Document '{os.path.basename(file_path)}' loaded successfully. Total text length: {len(self.document_text)} characters")
            
        except Exception as e:
            print(f"Error loading document '{file_path}': {str(e)}")
            raise
    
    def load_multiple_documents(self, file_paths):
        """Load multiple documents"""
        if not file_paths:
            raise ValueError("No file paths provided")
        
        print(f"Loading {len(file_paths)} documents...")
        successful_loads = 0
        
        for file_path in file_paths:
            try:
                self.load_document(file_path)
                successful_loads += 1
            except Exception as e:
                print(f"Failed to load '{file_path}': {str(e)}")
                continue
        
        print(f"Successfully loaded {successful_loads}/{len(file_paths)} documents")
        print(f"Total loaded files: {[os.path.basename(f) for f in self.loaded_files]}")
        return successful_loads
    
    def load_folder(self, folder_path):
        """Load all supported documents from a folder"""
        if not os.path.exists(folder_path):
            raise ValueError(f"Folder not found: {folder_path}")
        
        if not os.path.isdir(folder_path):
            raise ValueError(f"Path is not a directory: {folder_path}")
        
        supported_extensions = ['.pdf', '.docx', '.txt', '.md']
        file_paths = []
        
        print(f"Scanning folder: {folder_path}")
        
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in supported_extensions:
                    file_paths.append(file_path)
        
        if not file_paths:
            print(f"No supported documents found in folder. Supported formats: {', '.join(supported_extensions)}")
            return 0
        
        print(f"Found {len(file_paths)} supported documents in folder")
        self.folder_path = folder_path  # Store the folder path
        return self.load_multiple_documents(file_paths)
    
    def get_folder_files(self):
        """Get all files in the uploaded folder (both loaded and not loaded)"""
        if not self.folder_path:
            return []
        
        all_files = []
        for filename in os.listdir(self.folder_path):
            file_path = os.path.join(self.folder_path, filename)
            if os.path.isfile(file_path):
                file_info = {
                    'name': filename,
                    'path': file_path,
                    'loaded': file_path in self.loaded_files,
                    'supported': os.path.splitext(filename)[1].lower() in ['.pdf', '.docx', '.txt', '.md']
                }
                all_files.append(file_info)
        
        return sorted(all_files, key=lambda x: x['name'])
    
    def _load_pdf(self, file_path):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    def _load_docx(self, file_path):
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    
    def _load_text(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    
    def clear_documents(self):
        """Clear all loaded documents"""
        self.document_text = ""
        self.loaded_files = []
        self.folder_path = None
        print("All documents cleared.")
    
    def get_loaded_files(self):
        """Get list of loaded files"""
        return self.loaded_files.copy()
    
    def generate_answer(self, question):
        """Generate answer using all loaded documents"""
        if not self.document_text:
            raise ValueError("No documents loaded.")
        
        # Use the entire document - Gemini 2.0 Flash can handle ~1M tokens
        # But let's check if it's extremely large and warn if needed
        if len(self.document_text) > 1000000:  # ~1M characters
            print(f"Warning: Very large document collection ({len(self.document_text)} characters). This might exceed context limits.")
        
        prompt = f"""
        Based EXCLUSIVELY on the following document content, answer the question below.

        DOCUMENT CONTENT:
        {self.document_text}

        QUESTION: {question}

        Instructions:
        - Answer using ONLY information from the documents
        - Be comprehensive and accurate
        - If the answer cannot be found in the documents, say "The documents do not contain information about this"
        - Provide specific details and quotes when possible
        - Consider all document content in your answer
        - If multiple documents contain relevant information, synthesize the information
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "context length" in str(e).lower() or "too long" in str(e).lower():
                return self._handle_large_document(question)
            return f"Error generating answer: {str(e)}"
    
    def _handle_large_document(self, question):
        """Handle documents that are too large by using smart chunking"""
        print("Document collection too large, using smart chunking approach...")
        
        # Split document into manageable chunks
        chunks = self._split_document()
        answers = []
        
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")
            chunk_prompt = f"""
            Based on this portion of the documents, answer: {question}
            
            DOCUMENT PORTION:
            {chunk}
            
            Provide relevant information from this portion. If this portion doesn't contain relevant information, say "No relevant information in this portion".
            """
            
            try:
                response = self.model.generate_content(chunk_prompt)
                if "no relevant information" not in response.text.lower():
                    answers.append(response.text)
            except Exception as e:
                print(f"Error processing chunk {i+1}: {str(e)}")
        
        if not answers:
            return "No relevant information found in the documents."
        
        # Combine answers
        combined_prompt = f"""
        Combine these partial answers about the question: "{question}"
        
        PARTIAL ANSWERS:
        {' '.join(answers)}
        
        Provide a comprehensive final answer that synthesizes all the information:
        """
        
        try:
            final_response = self.model.generate_content(combined_prompt)
            return final_response.text
        except Exception as e:
            # If combining fails, return the first good answer
            return answers[0] if answers else "Could not generate a complete answer."
    
    def _split_document(self, chunk_size=20000):
        """Split document into chunks with overlap to maintain context"""
        chunks = []
        start = 0
        
        while start < len(self.document_text):
            end = start + chunk_size
            # Try to split at document boundary first
            if end < len(self.document_text):
                # Look for document separator
                doc_separator = self.document_text.rfind('--- Document:', start, end)
                if doc_separator != -1 and doc_separator > start:
                    end = doc_separator
                else:
                    # Look for a paragraph break
                    paragraph_break = self.document_text.rfind('\n\n', start, end)
                    if paragraph_break != -1:
                        end = paragraph_break
            
            chunk = self.document_text[start:end]
            chunks.append(chunk)
            start = end
        
        return chunks
    
    def interactive_mode(self):
        """Interactive Q&A session"""
        if not self.document_text:
            print("No documents loaded.")
            return
        
        print("\n" + "="*50)
        print("Gemini QA Mode - Type 'quit' to exit, 'files' to see loaded files, 'folder' to see all folder files, 'clear' to clear all documents")
        print("="*50)
        print(f"Total documents loaded: {len(self.loaded_files)}")
        if self.folder_path:
            print(f"Uploaded folder: {self.folder_path}")
        print(f"Total text size: {len(self.document_text)} characters")
        print("You can ask questions about all loaded documents.")
        
        while True:
            question = input("\nYour question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                break
            elif question.lower() in ['files', 'list']:
                print("\nLoaded files:")
                for i, file_path in enumerate(self.loaded_files, 1):
                    print(f"  {i}. {os.path.basename(file_path)}")
                continue
            elif question.lower() in ['folder', 'all files']:
                self._display_folder_files()
                continue
            elif question.lower() in ['clear', 'reset']:
                self.clear_documents()
                print("All documents cleared. You can load new documents.")
                break
            
            if not question:
                continue
            
            print("Generating answer...")
            answer = self.generate_answer(question)
            print(f"\nAnswer: {answer}")
    
    def _display_folder_files(self):
        """Display all files in the uploaded folder"""
        if not self.folder_path:
            print("No folder uploaded. Use option 7 to upload a folder.")
            return
        
        folder_files = self.get_folder_files()
        if not folder_files:
            print("No files found in the uploaded folder.")
            return
        
        print(f"\nAll files in folder: {self.folder_path}")
        print("="*60)
        print("Status: ✓ = Loaded, ✗ = Not loaded, ⚠ = Unsupported format")
        print("="*60)
        
        for file_info in folder_files:
            status = "✓" if file_info['loaded'] else ("⚠" if not file_info['supported'] else "✗")
            print(f"  {status} {file_info['name']}")
        
        loaded_count = sum(1 for f in folder_files if f['loaded'])
        supported_count = sum(1 for f in folder_files if f['supported'])
        print(f"\nSummary: {loaded_count}/{supported_count} supported files loaded")

def main():
    try:
        qa_system = GeminiDocumentQA()
        
        while True:
            print("\n" + "="*50)
            print("Gemini Document QA System")
            print("="*50)
            print("1. Load single document")
            print("2. Load multiple documents")
            print("3. View loaded documents")
            print("4. Clear all documents")
            print("5. Start Q&A session")
            print("6. Upload folder (load all supported documents)")
            print("7. View all files in uploaded folder")
            print("8. Exit")
            
            choice = input("\nChoose an option (1-8): ").strip()
            
            if choice == '1':
                file_path = input("Enter document path: ").strip()
                if not os.path.exists(file_path):
                    print("File not found.")
                else:
                    qa_system.load_document(file_path)
            
            elif choice == '2':
                file_paths_input = input("Enter document paths (separated by commas): ").strip()
                file_paths = [path.strip() for path in file_paths_input.split(',') if path.strip()]
                
                # Validate files exist
                valid_paths = []
                for path in file_paths:
                    if os.path.exists(path):
                        valid_paths.append(path)
                    else:
                        print(f"File not found: {path}")
                
                if valid_paths:
                    qa_system.load_multiple_documents(valid_paths)
                else:
                    print("No valid file paths provided.")
            
            elif choice == '3':
                loaded_files = qa_system.get_loaded_files()
                if loaded_files:
                    print("\nLoaded documents:")
                    for i, file_path in enumerate(loaded_files, 1):
                        print(f"  {i}. {os.path.basename(file_path)}")
                else:
                    print("No documents loaded.")
            
            elif choice == '4':
                qa_system.clear_documents()
            
            elif choice == '5':
                if not qa_system.get_loaded_files():
                    print("No documents loaded. Please load documents first.")
                else:
                    qa_system.interactive_mode()
            
            elif choice == '6':
                folder_path = input("Enter folder path: ").strip()
                if not os.path.exists(folder_path):
                    print("Folder not found.")
                else:
                    qa_system.load_folder(folder_path)
            
            elif choice == '7':
                qa_system._display_folder_files()
            
            elif choice == '8':
                print("Goodbye!")
                break
            
            else:
                print("Invalid choice. Please select 1-8.")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()