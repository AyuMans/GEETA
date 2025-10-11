#Web version of GEETA
import streamlit as st
import os
import sys
import google.generativeai as genai
from PyPDF2 import PdfReader
from docx import Document
import tempfile
import zipfile
from dotenv import load_dotenv
import shutil
# Add service-specific configuration
if 'win32service' in sys.modules or os.name == 'nt':
    # Running as Windows service - configure for headless operation
    import streamlit.web.bootstrap
    
    # Ensure proper temp directory for service
    service_temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "document_qa")
    os.makedirs(service_temp_dir, exist_ok=True)
    os.environ['TEMP'] = service_temp_dir
    
load_dotenv()

class GeminiDocumentQA:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('models/gemini-2.0-flash')
        self.document_text = ""
        self.loaded_files = []
        self.folder_path = None
    
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
            
            if self.document_text:
                self.document_text += f"\n\n--- Document: {os.path.basename(file_path)} ---\n\n{text}"
            else:
                self.document_text = f"--- Document: {os.path.basename(file_path)} ---\n\n{text}"
            
            self.loaded_files.append(file_path)
            return True, f"Document '{os.path.basename(file_path)}' loaded successfully!"
            
        except Exception as e:
            return False, f"Error loading document: {str(e)}"
    
    def load_uploaded_file(self, uploaded_file):
        """Load document from Streamlit uploaded file object"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name
            
            success, message = self.load_document(tmp_path)
            
            # Clean up temporary file
            os.unlink(tmp_path)
            
            return success, message
            
        except Exception as e:
            return False, f"Error processing file: {str(e)}"
    
    def load_folder(self, folder_path):
        """Load all supported documents from a folder"""
        if not os.path.exists(folder_path):
            return False, "Folder not found"
        
        if not os.path.isdir(folder_path):
            return False, "Path is not a directory"
        
        supported_extensions = ['.pdf', '.docx', '.txt', '.md']
        file_paths = []
        
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in supported_extensions:
                    file_paths.append(file_path)
        
        if not file_paths:
            return False, f"No supported documents found. Supported formats: {', '.join(supported_extensions)}"
        
        successful_loads = 0
        for file_path in file_paths:
            success, _ = self.load_document(file_path)
            if success:
                successful_loads += 1
        
        self.folder_path = folder_path
        return True, f"Successfully loaded {successful_loads}/{len(file_paths)} documents from folder"
    
    def get_folder_files_info(self):
        """Get information about all files in the uploaded folder"""
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
    
    def generate_answer(self, question):
        """Generate answer using all loaded documents"""
        if not self.document_text:
            return "No documents loaded. Please upload documents first."
        
        if len(self.document_text) > 1000000:
            st.warning("Very large document collection. This might take a while...")
        
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
            with st.spinner("Generating answer..."):
                response = self.model.generate_content(prompt)
                return response.text
        except Exception as e:
            if "context length" in str(e).lower() or "too long" in str(e).lower():
                return self._handle_large_document(question)
            return f"Error generating answer: {str(e)}"
    
    def _handle_large_document(self, question):
        """Handle documents that are too large by using smart chunking"""
        chunks = self._split_document()
        answers = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, chunk in enumerate(chunks):
            status_text.text(f"Processing chunk {i+1}/{len(chunks)}...")
            progress_bar.progress((i + 1) / len(chunks))
            
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
                continue
        
        progress_bar.empty()
        status_text.empty()
        
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
            return answers[0] if answers else "Could not generate a complete answer."
    
    def _split_document(self, chunk_size=20000):
        """Split document into chunks with overlap to maintain context"""
        chunks = []
        start = 0
        
        while start < len(self.document_text):
            end = start + chunk_size
            if end < len(self.document_text):
                doc_separator = self.document_text.rfind('--- Document:', start, end)
                if doc_separator != -1 and doc_separator > start:
                    end = doc_separator
                else:
                    paragraph_break = self.document_text.rfind('\n\n', start, end)
                    if paragraph_break != -1:
                        end = paragraph_break
            
            chunk = self.document_text[start:end]
            chunks.append(chunk)
            start = end
        
        return chunks

def extract_zip_folder(uploaded_zip):
    """Extract uploaded zip file to temporary directory"""
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Save uploaded zip file
        zip_path = os.path.join(temp_dir, "uploaded_folder.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.getvalue())
        
        # Extract zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Remove the zip file
        os.unlink(zip_path)
        
        return temp_dir
    except Exception as e:
        return None

def main():
    st.set_page_config(
        page_title="G.E.E.T.A",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .folder-upload {
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        border: 2px dashed #1f77b4;
        text-align: center;
    }
    .file-status {
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 0.8rem;
        margin: 2px;
    }
    .status-loaded {
        background-color: #d4edda;
        color: #155724;
    }
    .status-not-loaded {
        background-color: #fff3cd;
        color: #856404;
    }
    .status-unsupported {
        background-color: #f8d7da;
        color: #721c24;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">📚 G.E.E.T.A</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'qa_system' not in st.session_state:
        st.session_state.qa_system = GeminiDocumentQA()
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'temp_folders' not in st.session_state:
        st.session_state.temp_folders = []
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Document Management")
        
        # File upload section
        st.subheader("📄 Upload Individual Files")
        uploaded_files = st.file_uploader(
            "Choose files",
            type=['pdf', 'docx', 'txt', 'md'],
            accept_multiple_files=True,
            help="Supported formats: PDF, DOCX, TXT, MD"
        )
        
        if st.button("Upload Selected Files", type="primary", key="upload_files"):
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    success, message = st.session_state.qa_system.load_uploaded_file(uploaded_file)
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
            else:
                st.warning("Please select files to upload.")
        
        # Folder upload section
        st.markdown("---")
        st.subheader("📁 Upload Folder")
        
        st.markdown('<div class="folder-upload">', unsafe_allow_html=True)
        st.write("**Upload a ZIP folder containing documents**")
        uploaded_zip = st.file_uploader(
            "Choose a ZIP file",
            type=['zip'],
            key="folder_upload",
            help="Upload a ZIP file containing your documents"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("📂 Extract and Load Folder", type="primary", key="load_folder"):
            if uploaded_zip:
                with st.spinner("Extracting folder..."):
                    temp_dir = extract_zip_folder(uploaded_zip)
                    
                    if temp_dir:
                        st.session_state.temp_folders.append(temp_dir)
                        success, message = st.session_state.qa_system.load_folder(temp_dir)
                        
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.error("❌ Failed to extract ZIP file")
            else:
                st.warning("Please upload a ZIP file first.")
        
        # Clear documents
        st.markdown("---")
        if st.button("🗑️ Clear All Documents", type="secondary"):
            # Clean up temporary folders
            for temp_dir in st.session_state.temp_folders:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            
            st.session_state.temp_folders = []
            st.session_state.qa_system.clear_documents()
            st.session_state.chat_history = []
            st.success("All documents cleared!")
        
        # Document info
        st.markdown("---")
        st.subheader("📊 Document Info")
        if st.session_state.qa_system.loaded_files:
            st.write(f"**Loaded files:** {len(st.session_state.qa_system.loaded_files)}")
            st.write(f"**Text length:** {len(st.session_state.qa_system.document_text):,} characters")
            
            with st.expander("View Loaded Files"):
                for i, file_path in enumerate(st.session_state.qa_system.loaded_files, 1):
                    st.write(f"{i}. {os.path.basename(file_path)}")
            
            # Folder files info
            if st.session_state.qa_system.folder_path:
                with st.expander("📂 Folder Contents"):
                    folder_files = st.session_state.qa_system.get_folder_files_info()
                    if folder_files:
                        st.write("**All files in folder:**")
                        for file_info in folder_files:
                            if file_info['loaded']:
                                status_class = "status-loaded"
                                status_text = "✓ Loaded"
                            elif not file_info['supported']:
                                status_class = "status-unsupported"
                                status_text = "⚠ Unsupported"
                            else:
                                status_class = "status-not-loaded"
                                status_text = "✗ Not loaded"
                            
                            st.markdown(
                                f"<span class='file-status {status_class}'>{status_text}</span> {file_info['name']}",
                                unsafe_allow_html=True
                            )
        else:
            st.info("No documents loaded")
        
        # API Info
        st.markdown("---")
        st.subheader("⚙️ API Status")
        if st.session_state.qa_system.api_key:
            st.success("✅ Gemini API Connected")
        else:
            st.error("❌ Gemini API Key Missing")
            st.info("Set GEMINI_API_KEY in your .env file")
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("💬 Ask Questions")
        
        # Question input
        question = st.text_area(
            "Enter your question:",
            placeholder="What would you like to know about your documents?",
            height=100
        )
        
        if st.button("Get Answer", type="primary", disabled=not st.session_state.qa_system.loaded_files):
            if question.strip():
                answer = st.session_state.qa_system.generate_answer(question)
                
                # Add to chat history
                st.session_state.chat_history.append({
                    "question": question,
                    "answer": answer,
                    "files": len(st.session_state.qa_system.loaded_files)
                })
                
                # Display answer
                st.subheader("🤖 Answer:")
                st.write(answer)
            else:
                st.warning("Please enter a question.")
    
    with col2:
        st.header("📝 Chat History")
        
        if st.session_state.chat_history:
            for i, chat in enumerate(reversed(st.session_state.chat_history)):
                with st.expander(f"Q: {chat['question'][:50]}...", expanded=i==0):
                    st.write(f"**Question:** {chat['question']}")
                    st.write(f"**Answer:** {chat['answer']}")
                    st.caption(f"Based on {chat['files']} documents")
        else:
            st.info("No questions asked yet. Upload documents and ask questions to see history here.")
    
    # Quick stats at bottom
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Loaded Documents", len(st.session_state.qa_system.loaded_files))
    
    with col2:
        st.metric("Total Characters", f"{len(st.session_state.qa_system.document_text):,}")
    
    with col3:
        st.metric("Chat History", len(st.session_state.chat_history))
    
    with col4:
        folders_count = len(st.session_state.temp_folders)
        st.metric("Uploaded Folders", folders_count)

# Cleanup function
def cleanup_temp_folders():
    """Clean up temporary folders when the app closes"""
    if 'temp_folders' in st.session_state:
        for temp_dir in st.session_state.temp_folders:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

# Register cleanup
import atexit
atexit.register(cleanup_temp_folders)

if __name__ == "__main__":
    main()

