# 📚 GEETA - Generative Enhanced Examination & Text Analysis

<div align="center">

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.0+-red.svg)
![Google Gemini](https://img.shields.io/badge/Google-Gemini%20AI-4285F4.svg)

**An AI-powered document question-answering system that uses Google Gemini AI to intelligently analyze and answer questions about your documents.**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 🌟 Features

### Core Capabilities
- **🔄 Multi-Format Support**: Process PDF, DOCX, TXT, and Markdown files
- **🤖 AI-Powered Analysis**: Leverages Google Gemini 2.0 Flash for intelligent responses
- **💬 Interactive Q&A**: Real-time conversation interface with your documents
- **📁 Folder Processing**: Upload entire folders (via ZIP) for batch processing
- **🌐 Web Interface**: Beautiful Streamlit-based web UI
- **💻 CLI Mode**: Terminal-based interface for advanced users
- **📊 Smart Chunking**: Automatically handles large documents (1M+ characters)
- **🔒 Secure**: API keys stored safely in environment variables

### Interface Options
1. **Web Application** (`webgeeta.py`): Modern, user-friendly web interface
2. **CLI Application** (`pygeeta.py`): Command-line interface for terminal users
3. **Windows Service**: Run as a background service on Windows

---

## 📦 Installation

### Prerequisites
- Python 3.7 or higher
- Google Gemini API key ([Get free key here](https://aistudio.google.com/app/apikey))

### Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/AyuMans/geeta.git
   cd geeta
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Key**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env and add your Gemini API key
   # GEMINI_API_KEY=your_actual_api_key_here
   ```

---

## 🚀 Usage

### Web Application (Recommended)

```bash
streamlit run webgeeta.py
```

Then open your browser to `http://localhost:8501`

#### Web Interface Features:
- 📤 **Upload Files**: Drag and drop PDF, DOCX, TXT, or MD files
- 📂 **Upload Folders**: ZIP your document folder and upload all at once
- ✅️ **Select/Deselect Files**: Click to select the files for your Q&A
- 💬 **Ask Questions**: Get instant AI-powered answers
- 📜 **Chat History**: View previous questions and answers
- 📊 **Document Stats**: Track loaded documents and text size

### CLI Application

```bash
python pygeeta.py
```

#### CLI Features:
1. Load single document
2. Load multiple documents
3. View loaded documents
4. Clear all documents
5. Start Q&A session
6. Upload folder (load all supported documents)
7. View all files in uploaded folder
8. Exit

### Windows Service (Windows Only)

Run GEETA as a background service using NSSM:

```batch
# Run as Administrator
install_nssm.bat
```

**Service Management:**
- Start: `start_geeta.bat`
- Stop: `stop_geeta.bat`
- Status: `status_geeta.bat`

---

## 📖 Documentation

### Supported File Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| PDF | `.pdf` | Extracts text from all pages |
| Word Document | `.docx` | Processes full document text |
| Text File | `.txt` | Direct text processing |
| Markdown | `.md` | Markdown file support |

### Example Q&A Session

```python
from pygeeta import GeminiDocumentQA

# Initialize the system
qa = GeminiDocumentQA()

# Load documents
qa.load_document("research_paper.pdf")
qa.load_folder("my_documents/")

# Ask questions
answer = qa.generate_answer("What is the main conclusion?")
print(answer)
```

### Web Interface Example

1. **Upload Documents**
   - Click "Choose files" or drag & drop
   - Or upload a ZIP folder containing multiple documents

2. **Ask Questions**
   - Type your question in the text area
   - Click "Get Answer"
   - View the AI-generated response

3. **Review History**
   - Check the "Chat History" panel for previous Q&A
   - View which documents were used for each answer

---

## 🏗️ Project Structure

```
geeta/
├── webgeeta.py              # Streamlit web application
├── pygeeta.py               # CLI application
├── geeta_service.py         # Windows service (pywin32)
├── requirements.txt         # Python dependencies
├── .env.example            # Example environment configuration
├── .gitignore              # Git ignore rules
├── install_nssm.bat        # NSSM service installer
├── start_geeta.bat         # Start service
├── stop_geeta.bat          # Stop service
├── status_geeta.bat        # Check service status
└── README.md               # This file
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_actual_api_key_here
```

### Customization Options

**Web Application Port** (default: 8501):
```bash
streamlit run webgeeta.py --server.port=8080
```

**Model Selection**: Edit in `pygeeta.py` or `webgeeta.py`:
```python
self.model = genai.GenerativeModel('models/gemini-2.0-flash')
```

---

## 🎯 How It Works

1. **Document Loading**: Extracts text from various file formats
2. **Context Processing**: Combines all documents into a unified context
3. **AI Analysis**: Sends questions with full document context to Gemini AI
4. **Smart Response**: Returns comprehensive answers based solely on document content
5. **Large Document Handling**: Automatically chunks documents exceeding 1M characters

### Architecture

```
┌─────────────────┐
│  Upload Docs    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Text Extract   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Gemini AI      │◄───── User Question
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AI Answer      │
└─────────────────┘
```

---

## ⚠️ Important Notes

### Security
- ✅ Never commit `.env` file to version control
- ✅ Keep your API key private
- ✅ `.env` is automatically excluded via `.gitignore`
- ✅ Use `.env.example` as a template

### API Usage
- Free tier has usage limits
- Monitor usage at [Google AI Studio](https://aistudio.google.com)
- Large documents consume more tokens

### Performance
- **Small Documents** (<100K chars): Instant responses
- **Medium Documents** (100K-500K chars): 2-5 seconds
- **Large Documents** (500K-1M chars): 5-15 seconds
- **Very Large Documents** (>1M chars): Automatic chunking with progress indicators

---

## 🛠️ Troubleshooting

### Common Issues

**"API key not found"**
```bash
# Ensure .env file exists and contains:
GEMINI_API_KEY=your_actual_key_here
```

**"Unsupported file format"**
- Verify file extension is .pdf, .docx, .txt, or .md
- Check file isn't corrupted

**"Document processing is slow"**
- Large documents take longer to process
- Check your internet connection
- Verify Gemini API status

**Windows Service Issues**
- Run installation script as Administrator
- Check `service_error.log` for details
- Verify Python path in `install_nssm.bat`

---

## 📊 Performance Benchmarks

| Document Size | Processing Time | Response Time |
|--------------|----------------|---------------|
| 10K chars | <1 second | 1-2 seconds |
| 100K chars | 1-2 seconds | 2-4 seconds |
| 500K chars | 2-5 seconds | 5-10 seconds |
| 1M+ chars | 5-15 seconds | 10-20 seconds |

*Tested with Google Gemini 2.0 Flash on standard network connection*

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### Areas for Contribution
- Additional file format support
- UI/UX improvements
- Performance optimizations
- Documentation enhancements
- Bug fixes

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Google Gemini AI for powerful language models
- Streamlit for the amazing web framework
- PyPDF2 and python-docx for document processing
- The open-source community

---

## 📞 Support

- 🐛 **Bug Reports**: [Open an issue](https://github.com/AyuMans/geeta/issues)
- 💡 **Feature Requests**: [Start a discussion](https://github.com/AyuMans/geeta/discussions)
- 📧 **Contact**: [ayumansvit@gmail.com](https://mail.google.com/mail/u/0/?tab=rm&ogbl#inbox?compose=CllgCKCDBvxdwcXPscgMkGRNRBQWlVMMXVGlbmkgjdkcKBtFkkKbFSmlvWQHcQHvpPthrHpBFHL)

---

## 🗺️ Roadmap

- [ ] Support for more document formats (PPT, Excel, etc.)
- [ ] Multi-language support
- [ ] Cloud deployment guides (AWS, Azure, GCP)
- [ ] Docker containerization
- [ ] API endpoint for integrations
- [ ] Advanced search and filtering
- [ ] Document comparison features
- [ ] Export answers to various formats

---

<div align="center">

**⭐ If you find GEETA useful, please give it a star!**

Made with ❤️ using Python and Google Gemini AI

[⬆ Back to Top](#-geeta---generative-enhanced-examination--text-analysis)

</div>
