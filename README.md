(viewing in "Code" tab is recommended)

# Generative Enhanced Examination & Text Analysis (GEETA):

An AI-powered document question-answering system that uses Google Gemini AI to read and analyze your documents. Upload any PDF, DOCX, or TXT file and get intelligent answers to your questions instantly.

**GEETA** - *Generative Enhanced Examination & Text Analysis*

## 🚀 Features

- **📄 Multi-format Support**: Process PDF, DOCX, and TXT files
- **🤖 AI-Powered Answers**: Uses Google Gemini for intelligent, context-aware responses
- **💬 Interactive Q&A**: Real-time conversation with your documents
- **📚 Full Document Processing**: Handles large documents seamlessly
- **🔒 Secure**: API keys stored safely in environment variables
- **🆓 Free Tier**: Works with Google Gemini's free API tier

## 📦 Installation

### Prerequisites
- Python 3.7 or higher
- Google Gemini API key ([Get free key here](https://aistudio.google.com/app/apikey))

### Step-by-Step Setup

1. Clone the repository
   (bash)
   git clone https://github.com/yourusername/geeta.git
   cd geeta
   
2. Install dependencies
   pip install -r requirements.txt

3. Set up your API key
   # Copy the example environment file
   cp .env.example .env

   # Edit .env and add your API key
   # Open .env in a text editor and replace 'your_actual_key_here' with your real API key

**🎯Quick Start**
Interactive Mode(Recommended):

python program.py

Then follow the prompts:
1. Enter the Path to your document
2. Start asking questions in the interactive session
3. Type quit, exit, or q to end the session

**EXAMPLE SESSION**

Enter document path: C:/Documents/research_paper.pdf
Document loaded. Text length: 921431 characters

==================================================
Gemini QA Mode - Type 'quit' to exit
==================================================
Document size: 921431 characters

Your question: What is the main research question?
Generating answer...

Answer: The main research question focuses on the impact of machine learning algorithms...

**📁Supported File Formats**

Format	        Extension	                  Description
PDF	              .pdf	        Extracts text from all pages using PyPDF2
Word Document	    .docx	             Processes full document text
Text File	        .txt	               Direct text processing
Markdown	         .md	                Markdown file support


**🏗️How It Works**
1. GEETA uses a sophisticated approach to handle documents of any size:

2. Document Loading: Extracts text from PDF, DOCX, or TXT files

3. Full Context Processing: Uses the entire document content for accurate answers

4. Smart Chunking: For very large documents, automatically splits and processes in chunks

5. AI Analysis: Google Gemini AI analyzes the content and generates answers

6. Answer Synthesis: Combines insights from all document sections

**🔧Technical Details**
Core Components
1. GeminiDocumentQA class: Main class handling all operations

2. Document Loaders: Specialized handlers for each file format

3. Smart Chunking: Automatic handling of large documents (>1M characters)

4. Error Handling: Robust error management for API and file issues

Key Methods
1. load_document(file_path): Loads and processes documents

2. generate_answer(question): Generates AI-powered answers

3. interactive_mode(): Starts interactive Q&A session

4. _handle_large_document(): Automatic large document processing

**⚠️Important Security Notes**
1. Never commit your .env file to version control

2. Never share your API key publicly

3. The .env file is included in .gitignore for your safety

4. Even free API keys should be kept private to prevent abuse

**🐛Troubleshooting**
Common Issues
"API key not found"

# Make sure your .env file exists and contains:
GEMINI_API_KEY=your_actual_key_here

"Unsupported file format"

1. Ensure your file is PDF, DOCX, TXT, or MD format

2. Check that the file extension is correct

Document processing is slow

1. Very large documents may take longer to process

2. GEETA automatically uses chunking for documents >1M characters

API quota exceeded

1. Free tier has usage limits

2. Wait for quota reset or check your usage in Google AI Studio


**📊Performance**
1. Small Documents (<100K chars): Instant responses

2. Medium Documents (100K-500K chars): 2-5 seconds processing

3. Large Documents (500K-1M chars): 5-15 seconds with smart chunking

4. Very Large Documents (>1M chars): Automatic chunking with progress indicators

**📄 License**
This project is licensed under the MIT License - see the LICENSE file for details.



**⭐ If you find GEETA useful, please give it a star on GitHub!**

**💬 Have questions? Open an issue or start a discussion in the repository.**
