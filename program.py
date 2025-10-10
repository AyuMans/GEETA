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
    
    def load_document(self, file_path):
        """Load document from various formats"""
        file_extension = file_path.lower().split('.')[-1]
        
        try:
            if file_extension == 'pdf':
                self._load_pdf(file_path)
            elif file_extension == 'docx':
                self._load_docx(file_path)
            elif file_extension in ['txt', 'md']:
                self._load_text(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
                
            print(f"Document loaded. Text length: {len(self.document_text)} characters")
            
        except Exception as e:
            print(f"Error loading document: {str(e)}")
            raise
    
    def _load_pdf(self, file_path):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        self.document_text = text
    
    def _load_docx(self, file_path):
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        self.document_text = text
    
    def _load_text(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            self.document_text = file.read()
    
    def generate_answer(self, question):
        """Generate answer using the entire document"""
        if not self.document_text:
            raise ValueError("No document loaded.")
        
        # Use the entire document - Gemini 2.0 Flash can handle ~1M tokens
        # But let's check if it's extremely large and warn if needed
        if len(self.document_text) > 1000000:  # ~1M characters
            print(f"Warning: Very large document ({len(self.document_text)} characters). This might exceed context limits.")
        
        prompt = f"""
        Based EXCLUSIVELY on the following document content, answer the question below.

        DOCUMENT CONTENT:
        {self.document_text}

        QUESTION: {question}

        Instructions:
        - Answer using ONLY information from the document
        - Be comprehensive and accurate
        - If the answer cannot be found in the document, say "The document does not contain information about this"
        - Provide specific details and quotes when possible
        - Consider the entire document content in your answer
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
        print("Document too large, using smart chunking approach...")
        
        # Split document into manageable chunks
        chunks = self._split_document()
        answers = []
        
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")
            chunk_prompt = f"""
            Based on this portion of a document, answer: {question}
            
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
            return "No relevant information found in the document."
        
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
            # Try to split at paragraph boundary
            if end < len(self.document_text):
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
            print("No document loaded.")
            return
        
        print("\n" + "="*50)
        print("Gemini QA Mode - Type 'quit' to exit")
        print("="*50)
        print(f"Document size: {len(self.document_text)} characters")
        print("You can ask questions about the entire document content.")
        
        while True:
            question = input("\nYour question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                break
            
            if not question:
                continue
            
            print("Generating answer...")
            answer = self.generate_answer(question)
            print(f"\nAnswer: {answer}")

def main():
    try:
        qa_system = GeminiDocumentQA()
        file_path = input("Enter document path: ").strip()
        
        if not os.path.exists(file_path):
            print("File not found.")
            return
        
        qa_system.load_document(file_path)
        qa_system.interactive_mode()
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()