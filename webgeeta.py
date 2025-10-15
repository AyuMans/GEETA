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
import json
import os
from datetime import datetime
import secrets
import hashlib
import atexit

# Add service-specific configuration
if 'win32service' in sys.modules or os.name == 'nt':
    # Running as Windows service - configure for headless operation
    import streamlit.web.bootstrap
    
    # Ensure proper temp directory for service
    service_temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "document_qa")
    os.makedirs(service_temp_dir, exist_ok=True)
    os.environ['TEMP'] = service_temp_dir
    
load_dotenv()

# ===== USER MANAGEMENT AND CHAT HISTORY FUNCTIONS =====
class UserManager:
    def __init__(self):
        self.users_file = "users.json"
        self.chat_history_dir = "chat_histories"
        self.load_users()
        
        # Create chat history directory if it doesn't exist
        os.makedirs(self.chat_history_dir, exist_ok=True)
    
    def load_users(self):
        """Load users from JSON file"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r') as f:
                    self.users = json.load(f)
            else:
                self.users = {}
        except Exception:
            self.users = {}
    
    def save_users(self):
        """Save users to JSON file"""
        try:
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f, indent=2)
            return True
        except Exception:
            return False
    
    def hash_password(self, password):
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() + ':' + salt
    
    def verify_password(self, stored_password, provided_password):
        """Verify hashed password"""
        try:
            hashed, salt = stored_password.split(':')
            computed_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode(), salt.encode(), 100000).hex()
            return hashed == computed_hash
        except:
            return False
    
    def register_user(self, username, password):
        """Register a new user"""
        if username in self.users:
            return False, "Username already exists"
        
        if len(password) < 4:
            return False, "Password must be at least 4 characters"
        
        self.users[username] = {
            'password_hash': self.hash_password(password),
            'created_at': datetime.now().isoformat(),
            'last_login': None
        }
        
        if self.save_users():
            # Create empty chat history file for new user
            self.save_user_chat_history(username, [])
            return True, "Registration successful!"
        else:
            return False, "Registration failed - could not save user data"
    
    def login_user(self, username, password):
        """Login user"""
        if username not in self.users:
            return False, "User not found"
        
        if self.verify_password(self.users[username]['password_hash'], password):
            self.users[username]['last_login'] = datetime.now().isoformat()
            self.save_users()
            return True, "Login successful!"
        else:
            return False, "Invalid password"
    
    def user_exists(self):
        """Check if any users exist"""
        return len(self.users) > 0
    
    def get_user_chat_history_file(self, username):
        """Get the chat history file path for a user"""
        # Sanitize username to create safe filename
        safe_username = "".join(c for c in username if c.isalnum() or c in ('-', '_')).rstrip()
        return os.path.join(self.chat_history_dir, f"{safe_username}_history.json")
    
    def save_user_chat_history(self, username, chat_history):
        """Save chat history for a specific user"""
        try:
            history_file = self.get_user_chat_history_file(username)
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(chat_history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving chat history for {username}: {e}")
            return False
    
    def load_user_chat_history(self, username):
        """Load chat history for a specific user"""
        try:
            history_file = self.get_user_chat_history_file(username)
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading chat history for {username}: {e}")
        return []
    
    def clear_user_chat_history(self, username):
        """Clear chat history for a specific user"""
        try:
            history_file = self.get_user_chat_history_file(username)
            if os.path.exists(history_file):
                os.remove(history_file)
            return True
        except Exception as e:
            print(f"Error clearing chat history for {username}: {e}")
            return False

def save_chat_history():
    """Save chat history for current user"""
    try:
        if st.session_state.current_user:
            success = st.session_state.user_manager.save_user_chat_history(
                st.session_state.current_user, 
                st.session_state.chat_history
            )
            if not success:
                print("Failed to save chat history")
        else:
            print("No user logged in - cannot save chat history")
    except Exception as e:
        print(f"Error saving chat history: {e}")

def load_chat_history():
    """Load chat history for current user"""
    try:
        if st.session_state.current_user:
            history = st.session_state.user_manager.load_user_chat_history(
                st.session_state.current_user
            )
            print(f"Loaded {len(history)} chat history entries for {st.session_state.current_user}")
            return history
        else:
            print("No user logged in - cannot load chat history")
            return []
    except Exception as e:
        print(f"Error loading chat history: {e}")
        return []

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
atexit.register(cleanup_temp_folders)

# ===== MAIN APPLICATION CLASSES AND FUNCTIONS =====
class GeminiDocumentQA:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY environment variable.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('models/gemini-2.0-flash')
        self.document_text = ""
        self.loaded_files = []  # All loaded files
        self.enabled_files = []  # Files currently enabled for Q&A
        self.file_contents = {}  # Store file contents separately
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
            
            # Store file content separately
            self.file_contents[file_path] = text
            self.loaded_files.append(file_path)
            self.enabled_files.append(file_path)  # Enable by default
            
            # REBUILD DOCUMENT TEXT IMMEDIATELY AFTER ADDING FILE
            self._rebuild_document_text()
            
            return True, f"Document '{os.path.basename(file_path)}' loaded successfully!"
            
        except Exception as e:
            return False, f"Error loading document: {str(e)}"
    
    def toggle_file(self, file_path, enabled):
        """Enable or disable a file for Q&A"""
        if enabled and file_path not in self.enabled_files:
            self.enabled_files.append(file_path)
        elif not enabled and file_path in self.enabled_files:
            self.enabled_files.remove(file_path)
        
        # Rebuild document text from enabled files
        self._rebuild_document_text()
    
    def _rebuild_document_text(self):
        """Rebuild the combined document text from enabled files"""
        self.document_text = ""
        for file_path in self.enabled_files:
            if file_path in self.file_contents:
                if self.document_text:
                    self.document_text += f"\n\n--- Document: {os.path.basename(file_path)} ---\n\n{self.file_contents[file_path]}"
                else:
                    self.document_text = f"--- Document: {os.path.basename(file_path)} ---\n\n{self.file_contents[file_path]}"
    
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
    
    def load_folder_contents(self, folder_path):
        """Load all supported documents from a folder - FIXED VERSION"""
        if not os.path.exists(folder_path):
            return False, "Folder not found"
        
        if not os.path.isdir(folder_path):
            return False, "Path is not a directory"
        
        supported_extensions = ['.pdf', '.docx', '.txt', '.md']
        file_paths = []
        
        # Recursively search for files in the folder
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in supported_extensions:
                    file_paths.append(file_path)
        
        if not file_paths:
            return False, f"No supported documents found. Supported formats: {', '.join(supported_extensions)}"
        
        successful_loads = 0
        failed_loads = 0
        
        for file_path in file_paths:
            success, message = self.load_document(file_path)
            if success:
                successful_loads += 1
            else:
                failed_loads += 1
        
        self.folder_path = folder_path
        
        # REBUILD DOCUMENT TEXT AFTER LOADING ALL FILES
        self._rebuild_document_text()
        
        return True, f"Successfully loaded {successful_loads}/{len(file_paths)} documents from folder"
    
    def get_folder_files_info(self):
        """Get information about all files in the uploaded folder"""
        if not self.folder_path:
            return []
        
        all_files = []
        supported_extensions = ['.pdf', '.docx', '.txt', '.md']
        
        for root, dirs, files in os.walk(self.folder_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                file_info = {
                    'name': filename,
                    'path': file_path,
                    'loaded': file_path in self.loaded_files,
                    'enabled': file_path in self.enabled_files,
                    'supported': os.path.splitext(filename)[1].lower() in supported_extensions
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
        self.enabled_files = []
        self.file_contents = {}
        self.folder_path = None
    
    def remove_file(self, file_path):
        """Completely remove a file from the system"""
        if file_path in self.loaded_files:
            self.loaded_files.remove(file_path)
        if file_path in self.enabled_files:
            self.enabled_files.remove(file_path)
        if file_path in self.file_contents:
            del self.file_contents[file_path]
        self._rebuild_document_text()
    
    def generate_answer(self, question):
        """Generate answer using all enabled documents"""
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

def extract_and_process_zip(uploaded_zip):
    """Extract uploaded zip file and process all supported documents - FIXED VERSION"""
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
        st.error(f"Error extracting ZIP file: {str(e)}")
        return None

def main():
    # Initialize ALL session state variables at the start
    if 'user_manager' not in st.session_state:
        st.session_state.user_manager = UserManager()
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    
    if 'qa_system' not in st.session_state:
        st.session_state.qa_system = GeminiDocumentQA()
    
    if 'temp_folders' not in st.session_state:
        st.session_state.temp_folders = []
    
    if 'file_states' not in st.session_state:
        st.session_state.file_states = {}
    
    if 'show_history' not in st.session_state:
        st.session_state.show_history = False
    
    # Initialize chat history as EMPTY - we'll load it only after login
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Show login/register screen if not logged in
    if not st.session_state.logged_in:
        show_auth_screen()
        return
    
    # ONLY AFTER LOGIN: Load the user's specific chat history
    if st.session_state.logged_in and st.session_state.current_user:
        # Load chat history for the current user
        if not st.session_state.chat_history:  # Only load if empty
            st.session_state.chat_history = load_chat_history()
    
    # If logged in, show the main app
    show_main_application()
def show_auth_screen():
    """Show login or registration screen"""
    st.markdown("""
    <style>
    }
    .auth-title {
        text-align: center;
        font-size: 2.5rem;
        margin-bottom: 10px;
        background: linear-gradient(90deg, #fff, #f0f0f0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .auth-subtitle {
        text-align: center;
        margin-bottom: 30px;
        opacity: 0.9;
    }
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 3rem;
        font-size: 1.1rem;
        margin-top: 10px;
    }
    .secondary-btn {
        background-color: transparent !important;
        border: 2px solid white !important;
        color: white !important;
    }
    .secondary-btn:hover {
        background-color: rgba(255,255,255,0.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    
    # Check if users exist to show login, otherwise show registration
    users_exist = st.session_state.user_manager.user_exists()
    
    # Check if we should show registration form (either no users exist or user clicked "Create New Account")
    show_registration = not users_exist or st.session_state.get('show_register', False)
    
    if show_registration:
        # Registration form
        st.markdown('<h1 class="auth-title">👋 Welcome to G.E.E.T.A</h1>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Create your account to get started</p>', unsafe_allow_html=True)
        
        with st.form("register_form"):
            username = st.text_input("👤 Choose a username", placeholder="Enter your username")
            password = st.text_input("🔑 Create password", type="password", placeholder="Enter your password")
            confirm_password = st.text_input("✅ Confirm password", type="password", placeholder="Re-enter your password")
            
            submitted = st.form_submit_button("🚀 Create Account & Start", use_container_width=True)
            
            if submitted:
                if not username or not password:
                    st.error("❌ Please fill in all fields")
                elif password != confirm_password:
                    st.error("❌ Passwords don't match")
                else:
                    success, message = st.session_state.user_manager.register_user(username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.current_user = username
                        st.session_state.show_register = False  # Reset the flag
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        # If users exist, show option to go back to login
        if users_exist:
            if st.button("⬅️ Back to Login", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()
    
    else:
        # Login for existing users
        st.markdown('<h1 class="auth-title">🔒 Welcome Back</h1>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Sign in to access your documents</p>', unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("👤 Username", placeholder="Enter your username")
            password = st.text_input("🔑 Password", type="password", placeholder="Enter your password")
            
            submitted = st.form_submit_button("🚀 Sign In", use_container_width=True)
            
            if submitted:
                if not username or not password:
                    st.error("❌ Please fill in all fields")
                else:
                    success, message = st.session_state.user_manager.login_user(username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.current_user = username
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        # Option to create new account
        if st.button("📝 Create New Account", use_container_width=True, key="create_account_btn"):
            st.session_state.show_register = True
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_main_application():
    """Show the main application after login"""
    # Set page config only once at the beginning
    st.set_page_config(
        page_title="G.E.E.T.A",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Add user info to sidebar
    with st.sidebar:
        st.success(f"👤 Signed in as: **{st.session_state.current_user}**")
        if st.button("🚪 Logout", use_container_width=True):
            # Save chat history before logging out
            save_chat_history()
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.chat_history = []  # Clear chat history on logout
            st.rerun()
        st.markdown("---")
    
    
    # Custom CSS with glowy effects (your existing CSS)
    st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        background: linear-gradient(90deg, #1f77b4, #ff7f0e, #2ca02c, #d62728);
        background-size: 400% 400%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 800;
        animation: gradientShift 8s ease infinite;
        text-shadow: 0 0 20px rgba(31, 119, 180, 0.3);
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
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
    .zip-info {
        background-color: #e7f3ff !important;
        padding: 15px !important;
        border-radius: 8px !important;
        border-left: 4px solid #1f77b4 !important;
        margin: 10px 0 !important;
        color: #6b95cf !important;
        font-size: 16px !important;
    }
    .file-list {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .file-item {
        display: flex;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #e9ecef;
    }
    .file-item:last-child {
        border-bottom: none;
    }
    .file-checkbox {
        margin-right: 10px;
    }
    .file-name {
        flex-grow: 1;
    }
    .remove-btn {
        margin-left: 10px;
    }
    
    /* Glowing effect for headers */
    .glow-header {
        font-size: 1.8rem;
        color: #1f77b4;
        text-shadow: 0 0 10px rgba(31, 119, 180, 0.7);
        margin-bottom: 1rem;
        border-bottom: 2px solid rgba(31, 119, 180, 0.3);
        padding-bottom: 0.5rem;
    }
    
    /* Glowing buttons */
    .stButton > button {
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        box-shadow: 0 0 15px rgba(31, 119, 180, 0.4);
    }
    
    /* Override Streamlit's default white background for divs */
    div[data-testid="stMarkdownContainer"] div {
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display the main header ONLY ONCE
    st.markdown('<h1 class="main-header">📚 G.E.E.T.A</h1>', unsafe_allow_html=True)
    
    # Initialize session state for the main app
  
    
    
    # Sidebar with tabs
    with st.sidebar:
        # History button at the top
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("📜 History", use_container_width=True, type="primary" if st.session_state.show_history else "secondary"):
                st.session_state.show_history = not st.session_state.show_history
                st.rerun()
        
        st.markdown("---")
        
        if st.session_state.show_history:
            # History view
            st.markdown('<h2 class="glow-header">📜 Chat History</h2>', unsafe_allow_html=True)
            
            if not st.session_state.chat_history:
                st.info("No questions asked yet. Ask questions to see history here.")
            else:
                # Display chat history
                for i, chat in enumerate(reversed(st.session_state.chat_history)):
                    with st.expander(f"Q: {chat['question'][:50]}...", expanded=i==0):
                        st.write(f"**Question:** {chat['question']}")
                        st.write(f"**Answer:** {chat['answer']}")
                        st.caption(f"Based on {chat['files']} documents")
                
                # Clear history button
                if st.button("🗑️ Clear History", type="secondary", use_container_width=True):
                    st.session_state.chat_history = []
                    save_chat_history()
                    st.success("Chat history cleared!")
                    st.rerun()
            
            st.markdown("---")
        
        else:
            # Normal document management view
            st.header("📁 Document Management")
            
            # Create tabs
            tab1, tab2, tab3 = st.tabs(["📄 Individual Files", "📁 ZIP Folder", "⚡ Active Files"])
            
            # Tab 1: Individual Files
            with tab1:
                st.subheader("Upload Individual Files")
                uploaded_files = st.file_uploader(
                    "Choose files",
                    type=['pdf', 'docx', 'txt', 'md'],
                    accept_multiple_files=True,
                    help="Supported formats: PDF, DOCX, TXT, MD",
                    key="individual_files"
                )
                
                if st.button("Upload Selected Files", type="primary", key="upload_files"):
                    if uploaded_files:
                        success_count = 0
                        for uploaded_file in uploaded_files:
                            success, message = st.session_state.qa_system.load_uploaded_file(uploaded_file)
                            if success:
                                st.success(f"✅ {message}")
                                success_count += 1
                            else:
                                st.error(f"❌ {message}")
                        if success_count > 0:
                            st.success(f"🎉 Successfully loaded {success_count} files!")
                            st.rerun()
                    else:
                        st.warning("Please select files to upload.")
                
                # Quick actions for individual files tab
                if st.session_state.qa_system.loaded_files:
                    st.markdown("---")
                    st.subheader("Quick Actions")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✅ Enable All", use_container_width=True, key="enable_all_tab1"):
                            st.session_state.qa_system.enabled_files = st.session_state.qa_system.loaded_files.copy()
                            st.session_state.qa_system._rebuild_document_text()
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ Disable All", use_container_width=True, key="disable_all_tab1"):
                            st.session_state.qa_system.enabled_files = []
                            st.session_state.qa_system._rebuild_document_text()
                            st.rerun()
            
            # Tab 2: ZIP Folder
            with tab2:
                st.subheader("Upload ZIP Folder")
                
                st.markdown('<div class="folder-upload">', unsafe_allow_html=True)
                st.write("**Upload a ZIP file containing documents**")
                st.markdown("""
                <div class="zip-info">
                <strong>📦 ZIP File Requirements:</strong><br>
                • Can contain PDF, DOCX, TXT, MD files<br>
                • Supports nested folders<br>
                • Files are automatically extracted and processed
                </div>
                """, unsafe_allow_html=True)
                
                uploaded_zip = st.file_uploader(
                    "Choose a ZIP file",
                    type=['zip'],
                    key="folder_upload",
                    help="Upload a ZIP file containing your documents (PDF, DOCX, TXT, MD)"
                )
                st.markdown('</div>', unsafe_allow_html=True)
                
                if st.button("📂 Extract and Load ZIP Contents", type="primary", key="load_zip"):
                    if uploaded_zip:
                        with st.spinner("Extracting ZIP file and processing documents..."):
                            # Extract ZIP to temporary directory
                            temp_dir = extract_and_process_zip(uploaded_zip)
                            
                            if temp_dir:
                                # Store temp directory for cleanup
                                st.session_state.temp_folders.append(temp_dir)
                                
                                # Load all supported documents from the extracted folder
                                success, message = st.session_state.qa_system.load_folder_contents(temp_dir)
                                
                                if success:
                                    st.success(f"✅ {message}")
                                    st.info(f"📁 Extracted to temporary folder: {os.path.basename(temp_dir)}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                            else:
                                st.error("❌ Failed to extract ZIP file. Please check if it's a valid ZIP archive.")
                    else:
                        st.warning("Please upload a ZIP file first.")
                
                # Quick actions for ZIP folder tab
                if st.session_state.qa_system.loaded_files:
                    st.markdown("---")
                    st.subheader("Quick Actions")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✅ Enable All", use_container_width=True, key="enable_all_tab2"):
                            st.session_state.qa_system.enabled_files = st.session_state.qa_system.loaded_files.copy()
                            st.session_state.qa_system._rebuild_document_text()
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ Disable All", use_container_width=True, key="disable_all_tab2"):
                            st.session_state.qa_system.enabled_files = []
                            st.session_state.qa_system._rebuild_document_text()
                            st.rerun()
            
            # Tab 3: Active Files Management
            with tab3:
                if st.session_state.qa_system.loaded_files:
                    st.subheader("File Management")
                    st.info("Click on file names to enable/disable them for Q&A")
                    
                    # Quick actions
                    st.write("**Quick Actions:**")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✅ Enable All", use_container_width=True, key="enable_all_tab3"):
                            st.session_state.qa_system.enabled_files = st.session_state.qa_system.loaded_files.copy()
                            st.session_state.qa_system._rebuild_document_text()
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ Disable All", use_container_width=True, key="disable_all_tab3"):
                            st.session_state.qa_system.enabled_files = []
                            st.session_state.qa_system._rebuild_document_text()
                            st.rerun()
                    
                    # Display files as clickable items
                    with st.container():
                        st.markdown('<div class="file-list">', unsafe_allow_html=True)
                        
                        files_to_remove = []
                        
                        for file_path in st.session_state.qa_system.loaded_files:
                            col1, col2 = st.columns([6, 1])
                            
                            # Get current enabled state
                            current_enabled = file_path in st.session_state.qa_system.enabled_files
                            
                            with col1:
                                # Create a unique key for each file button
                                file_button_key = f"file_toggle_{file_path}"
                                
                                # Determine button label and style based on enabled state
                                if current_enabled:
                                    button_label = f"✅ {os.path.basename(file_path)}"
                                    button_type = "primary"
                                else:
                                    button_label = f"❌ {os.path.basename(file_path)}"
                                    button_type = "secondary"
                                
                                # Clickable file button to toggle selection
                                if st.button(button_label, key=file_button_key, use_container_width=True, type=button_type):
                                    st.session_state.qa_system.toggle_file(file_path, not current_enabled)
                                    st.rerun()
                            
                            with col2:
                                if st.button("🗑️", key=f"remove_{file_path}", help="Remove file"):
                                    files_to_remove.append(file_path)
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Remove files after iteration
                        for file_path in files_to_remove:
                            st.session_state.qa_system.remove_file(file_path)
                            st.success(f"Removed: {os.path.basename(file_path)}")
                            st.rerun()
                else:
                    st.info("No documents loaded. Upload files or a ZIP folder to get started.")
            
            # Clear documents (outside tabs)
            st.markdown("---")
            if st.button("🗑️ Clear All Documents", type="secondary", use_container_width=True):
                # Clean up temporary folders
                for temp_dir in st.session_state.temp_folders:
                    if os.path.exists(temp_dir):
                        try:
                            shutil.rmtree(temp_dir)
                        except:
                            pass
                
                # Clear file states
                st.session_state.file_states = {}
                st.session_state.temp_folders = []
                st.session_state.qa_system.clear_documents()               
                st.success("All documents cleared!")
                st.rerun()
            
            # Document info
            st.markdown("---")
            st.subheader("📊 Document Info")
            if st.session_state.qa_system.loaded_files:
                enabled_count = len(st.session_state.qa_system.enabled_files)
                total_count = len(st.session_state.qa_system.loaded_files)
                st.write(f"**Active files:** {enabled_count}/{total_count}")
                st.write(f"**Text length:** {len(st.session_state.qa_system.document_text):,} characters")
                
                with st.expander("📂 ZIP Contents Overview"):
                    if st.session_state.qa_system.folder_path:
                        folder_files = st.session_state.qa_system.get_folder_files_info()
                        if folder_files:
                            loaded_count = sum(1 for f in folder_files if f['loaded'])
                            enabled_count = sum(1 for f in folder_files if f.get('enabled', False))
                            supported_count = sum(1 for f in folder_files if f['supported'])
                            total_count = len(folder_files)
                            
                            st.write(f"**ZIP Statistics:**")
                            st.write(f"• Total files: {total_count}")
                            st.write(f"• Supported formats: {supported_count}")
                            st.write(f"• Successfully loaded: {loaded_count}")
                            st.write(f"• Currently enabled: {enabled_count}")
            else:
                st.info("No documents loaded. Upload files or a ZIP folder to get started.")
            
            # API Info
            st.markdown("---")
            st.subheader("⚙️ API Status")
            if st.session_state.qa_system.api_key:
                st.success("✅ Gemini API Connected")
            else:
                st.error("❌ Gemini API Key Missing")
                st.info("Set GEMINI_API_KEY in your .env file")
    
    # Main content area - only question input now
    st.markdown('<h2 class="glow-header">💬 Ask Questions</h2>', unsafe_allow_html=True)
    
    # Show active files info
    if st.session_state.qa_system.enabled_files:
        enabled_files_list = [os.path.basename(f) for f in st.session_state.qa_system.enabled_files]
        st.info(f"**Q&A will use:** {', '.join(enabled_files_list[:3])}{'...' if len(enabled_files_list) > 3 else ''}")
    else:
        st.warning("⚠️ No files are currently enabled for Q&A. Please enable files from the sidebar.")
    
    # Question input
    question = st.text_area(
        "Enter your question:",
        placeholder="What would you like to know about your documents?",
        height=100
    )
    
    if st.button("Get Answer", type="primary", disabled=not st.session_state.qa_system.enabled_files):
        if question.strip():
            # Double-check that we have document text
            if not st.session_state.qa_system.document_text.strip():
                st.error("No document content available. Please make sure files are properly loaded and enabled.")
            else:
                answer = st.session_state.qa_system.generate_answer(question)
                
                # Add to chat history
                st.session_state.chat_history.append({
                    "question": question,
                    "answer": answer,
                    "files": len(st.session_state.qa_system.enabled_files)
                })
                save_chat_history()
                # Display answer
                st.subheader("🤖 Answer:")
                st.write(answer)
        else:
            st.warning("Please enter a question.")
    
    # Quick stats at bottom
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Loaded Documents", len(st.session_state.qa_system.loaded_files))
    
    with col2:
        st.metric("Active Documents", len(st.session_state.qa_system.enabled_files))
    
    with col3:
        st.metric("Chat History", len(st.session_state.chat_history))
    
    with col4:
        folders_count = len(st.session_state.temp_folders)
        st.metric("Uploaded ZIPs", folders_count)
        



if __name__ == "__main__":
    main()