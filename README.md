# AI College Assistant Pro

An intelligent RAG (Retrieval-Augmented Generation) assistant for college documents, transcripts, marksheets, and syllabus PDFs. Built with **FastAPI**, **PostgreSQL + pgvector**, **Sentence Transformers**, and **Google Gemini API**.

---


1. Open this folder in **VS Code**: `File` -> `Open Folder...` -> Select `AI College Assistant`.
2. VS Code is pre-configured to automatically use the local virtual environment (`myenv`).
3. Either:
   - Press **`F5`** on your keyboard, OR
   - Open [main.py](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/main.py) and click the **Run / Play** button in the top-right corner.
4. Open your browser and visit: **[http://127.0.0.1:8000/chat](http://127.0.0.1:8000/chat)**.

---

### Option 3: Running from PowerShell or Command Prompt
Open your terminal in this directory and run:

```powershell
.\myenv\Scripts\python.exe main.py
```

Or activate the environment first:
```powershell
.\myenv\Scripts\activate
python main.py
```

Then visit **`http://127.0.0.1:8000/chat`**.

---

## 🗄️ Database (Docker)
The vector database runs on PostgreSQL with `pgvector`:
- **Start DB:** `docker-compose up -d`
- **Stop DB:** `docker-compose down`

---

## ⚙️ Environment Configuration (`.env`)
Your `.env` file should contain:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash
```

---

## 📂 Project Structure
- [main.py](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/main.py) - FastAPI backend server, vector search, and Gemini streaming API
- [database.py](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/database.py) - PostgreSQL connection and table initialization
- [chat.html](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/chat.html) - Web chat interface with streaming responses and drag & drop PDF upload
- [extractor.py](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/extractor.py) - Hybrid text extractor (pdfplumber + OCR for scanned PDFs)
- [chunker.py](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/chunker.py) - Text chunker for semantic retrieval
- [ingest.py](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/ingest.py) - Batch ingestion script for PDFs in the `data/` folder
- [run.bat](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/run.bat) - One-click Windows runner
- [.vscode/](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/.vscode/) - VS Code launch and interpreter settings
- [requirements.txt](file:///c:/Users/HP/OneDrive/Desktop/AI%20College%20Assistant/requirements.txt) - Python dependency list
