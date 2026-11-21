# 🎓 AI College Academic Assistant (UTU)

An intelligent, document-grounded artificial intelligence assistant designed specifically for university students, faculty, and academic administration. The system allows users to interact either through a modern chat interface or completely hands-free by voice using **"Hello Buddy"** mode. It answers questions about course syllabus, subjects, credits, examination schedules, and official university holiday calendars with 100% verified accuracy.

---

## 📌 Project Overview

### What Does This Project Do?
When students need to know syllabus topics, course credit requirements, or upcoming university holiday dates, they typically have to scroll through 200+ page PDF circulars. 

Traditional generic chatbots (like standard ChatGPT) hallucinate or mix up syllabus regulations from different universities. **AI College Academic Assistant** solves this problem using **Retrieval-Augmented Generation (RAG)**. It searches through official university PDFs stored in a PostgreSQL vector database (`pgvector`) and gives direct, accurate answers grounded in official college documents.

### 🛡️ Privacy & Safety First
For student security and privacy, private student records (such as personal marksheets, private contact info, and grades) are kept strictly confidential and are not exposed. The assistant is dedicated exclusively to official university academic information:
1. **Official University Syllabus (B.Tech):** Course subjects, credit schemes, unit modules, and practical lab requirements.
2. **Official Academic & Holiday Calendar:** Gazetted university holidays, semester breaks, and examination schedules.

---

## 🚀 Why This Project is Better Than General AI Chatbots

| Feature / Capability | General AI Chatbots (ChatGPT / Standard LLMs) | Generic College Chatbots | 🌟 AI College Assistant (UTU) |
|---|---|---|---|
| **Syllabus Accuracy** | ❌ **High Hallucination:** Guesses general syllabus; mixes up US, foreign, or different state university syllabus topics. | ⚠️ **Rigid Keyword Match:** Fails if the student doesn't type exact keywords. | ✅ **100% Grounded:** Retrieves the exact unit and credits from the official university syllabus PDF via pgvector. |
| **University Holiday Calendar** | ❌ **No Local Knowledge:** Has no knowledge of specific state university circulars or gazetted holiday dates. | ❌ Static list that breaks when university schedules change. | ✅ **Exact Calendar Retrieval:** Accurately answers university holiday dates, vacation schedules, and examination periods. |
| **Voice Response Delay** | ⏳ **Slow (5–8 seconds):** Waits for the entire text paragraph to generate before starting text-to-speech. | ❌ No voice interaction (text only). | ⚡ **Sub-Second (<1s):** Starts speaking sentence 1 within ~1 second using live streaming sentence audio queue. |
| **Voice Barge-In (Interruption)** | ❌ **Cannot Interrupt:** You must wait until it finishes speaking, or clicking stop breaks the session. | ❌ Not available. | 🎙️ **Full Voice Interruption:** Say *"Stop"*, *"रुको"*, or ask a new question in the middle of speech; voice cuts off instantly. |
| **Acoustic Echo Rejection** | ❌ **Feedback Loop:** Microphone picks up the AI's voice from laptop speakers and re-types it into chat. | ❌ Not available. | 🛡️ **Zero Echo Loop:** Smart acoustic filter and similarity check prevent speaker output from re-entering the microphone. |
| **Privacy & Student Safety** | ⚠️ Often trains on user queries; student data risk. | ⚠️ Unencrypted local files. | 🛡️ **Privacy-First:** Personal records are isolated and omitted from public models. |
| **Cloud Hosting Cost** | 💸 Heavy multi-gigabyte models requiring expensive GPUs ($50–$200/mo). | ⚠️ Expensive cloud dependencies. | 🚀 **Ultra-Lightweight:** FastEmbed ONNX runs within ~75MB RAM on free/low-tier cloud (Render 512MB RAM tier). |

---

## 🔄 How It Works: The 3-Step Pipeline

```
[Student Input: Voice or Text]
               │
               ▼
[Semantic Embedding Engine (FastEmbed ONNX)]
               │
               ▼
[Vector Database Search (PostgreSQL pgvector HNSW Index)]
               │
               ▼
[LLM Reasoning & Synthesis (Gemini 3.5 Flash)]
               │
       ┌───────┴───────┐
       ▼               ▼
[Live Markdown     [Parallel Sentence TTS
 Streaming in UI]   Audio Streaming (<1s)]
```

### Stage 1: Question Input (Text or Voice)
* **Text Mode:** The student types an academic question into the input box (e.g., *"What subjects are in 3rd semester CSE?"* or *"When does Diwali break start?"*).
* **Voice Mode ("Hello Buddy"):** Click the **Hello Buddy** button in the top bar. Speak naturally in English or Hinglish. When you finish speaking, the system automatically detects silence and submits the question.

### Stage 2: Knowledge Retrieval (RAG Pipeline)
1. **Semantic Search:** The question is converted into mathematical vector coordinates using FastEmbed ONNX.
2. **Intent Guardrails:** 
   - Casual greetings (*"hi"*, *"whatsup buddy"*) receive warm, polite greetings without pulling unrelated document chunks.
   - Private record queries are safely redirected to public academic information.
3. **Database Lookup:** The system queries PostgreSQL `pgvector` to find matching chunks from official syllabus and calendar documents.
4. **AI Generation:** The retrieved verified context is passed to Gemini 3.5 Flash, which formulates a direct, concise response.

### Stage 3: Output Delivery (Synchronized Text & Speech)
* **Visual Output:** Markdown text streams in real-time with formatted bullet points, tables, and verified source badges.
* **Audio Output:** Text sentences are sent in parallel to the custom cloned voice engine. Sentence 1 begins speaking within ~1 second while remaining sentences stream in the background.
* **Acoustic Filtering:** The system listens for voice commands (*"Stop"*, *"रुको"*, *"बस"*) or new questions during playback and halts speech immediately.

---

## 📁 File-by-File Breakdown & Architecture

Here is what every file in this project does:

### 1. `main.py` — Central Backend Server
* **Role:** The main API server coordinating frontend requests, database vector search, Gemini generation, and text-to-speech.
* **Key Endpoints:**
  * `POST /ask`: Receives user queries, runs vector similarity search, and streams back token responses.
  * `POST /tts`: Generates cloned human voice audio for individual sentences.
  * `GET /api/documents`: Returns the list of currently indexed official documents.
* **Output:** Live FastAPI server running on port 8000 (local) or port 10000 (Render).

### 2. `chat.html` — Frontend User Interface
* **Role:** The responsive web interface that students interact with in their browser.
* **Key Features:**
  * Clean, professional **Rose-White** theme designed for academic institutions.
  * **"Hello Buddy"** voice assistant with real-time audio visualization.
  * Sentence-by-sentence parallel audio queue for sub-second speech response.
  * Acoustic echo filter that prevents speaker feedback loops.
  * Markdown rendering, syllabus tables, and source verification drawers.
* **Output:** Interactive web application rendered in Chrome, Edge, or Brave.

### 3. `database.py` — Database Connection & Vector Engine
* **Role:** Manages connection pooling and table initialization for PostgreSQL with the `pgvector` extension.
* **Output:** Creates and manages the `college_docs` table with HNSW vector indexing.

### 4. `extractor.py` — Hybrid Document Extractor
* **Role:** Extracts clean digital text from university PDF documents using `pdfplumber` with Tesseract OCR fallback for scanned pages.
* **Output:** Clean text strings ready for chunking.

### 5. `chunker.py` — Semantic Document Chunker
* **Role:** Breaks long document text into overlapping token windows (150–200 words) so vector search can locate exact paragraphs.
* **Output:** Array of text chunks with metadata.

### 6. `ingest.py` — Document Ingestion Utility
* **Role:** Reads PDF files from the `data/` folder, extracts text, chunks it, generates vector embeddings, and stores them in PostgreSQL.
* **Output:** Fully indexed vector database.

### 7. `Dockerfile` — Production Container
* **Role:** Containerizes the application on Python 3.11-slim with pre-cached ONNX embedding models for fast boot times on cloud platforms like Render.
* **Output:** Production Docker container image.

---

## 🛠️ How to Run Locally

### 1. Clone the Repository
```bash
git clone https://github.com/Pankajsaini90454/AI-COLLEGE-ASSISTANT-UTU-.git
cd AI-COLLEGE-ASSISTANT-UTU-
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://username:password@host:5432/dbname
PORT=8000
```

### 4. Ingest Official Documents
Place your university syllabus and holiday calendar PDFs in the `data/` directory, then run:
```bash
python ingest.py
```

### 5. Start the Server
```bash
python main.py
```
Open your browser and navigate to: **`http://localhost:8000`**

---

## 🌐 Cloud Deployment (Render)

1. Connect your GitHub repository to **Render**.
2. Select **Web Service** with **Docker** environment.
3. In the **Environment Variables** tab, add:
   - `GEMINI_API_KEY`: Your Google Gemini API key.
   - `DATABASE_URL`: Your cloud PostgreSQL (pgvector) connection string.
4. Click **Deploy**. Render will build the Docker container and make the service live.

---

## 📄 License
This project is built for university students and academic administration under the MIT License.
