# AI College Assistant (UTU)

An intelligent, document-grounded artificial intelligence assistant designed specifically for college students, faculty, and academic administration. The system allows users to interact either through a modern chat interface or completely by voice using **"Hello Buddy"** mode, answering questions about college syllabus, exam schedules, marksheets, personal academic profile, and official university notices with 100% accuracy.

---

## 📌 Project Overview & Summary

### What Does This Project Do?
Traditional chatbots often hallucinate (make up facts) when asked specific questions about university courses, marksheets, or syllabus regulations. 

**AI College Assistant (UTU)** solves this problem using **Retrieval-Augmented Generation (RAG)**. Instead of guessing, the AI connects to a verified university knowledge base stored in a high-speed vector database. Whenever a user asks a question, the assistant finds the exact page and paragraph from official college PDFs, marksheets, and student profile records, and provides an answer grounded strictly in verified university sources.

In addition, it features a personalized, human-like voice interface powered by **AI Voice Cloning**. When interacting in voice mode, the assistant speaks back using a realistic cloned voice rather than a robotic text-to-speech engine.

---

## 🔄 How It Works: The End-to-End Workflow

The journey of every user question through the system follows three simple, coordinated stages:

### Stage 1: Question Input (Text or Voice)
* **Text Mode:** The user types any academic or college query in the input box (e.g., *"What is my semester GPA?"* or *"Explain Unit 3 of Cloud Computing syllabus"*).
* **Voice Mode ("Hello Buddy"):** The user clicks the **Hello Buddy** button in the top bar. The browser begins listening through the microphone. The user speaks naturally in English or Hinglish. When the user finishes speaking, the system automatically detects the silence and submits the question.

### Stage 2: Processing & Knowledge Retrieval (RAG Pipeline)
1. **Semantic Search (Vector Engine):** The user's question is converted into mathematical meaning (vector embedding) using an ultra-lightweight embedding model.
2. **Database Lookup:** The system searches a cloud-hosted PostgreSQL vector database (`pgvector`) to find the top matching chunks of text from official syllabus PDFs, previous year marksheets, and notices.
3. **Fact Retrieval:** The system retrieves the student's personal profile (name, college name, branch, graduation year) from persistent long-term memory.
4. **AI Generation:** The retrieved document passages, user memories, and chat history are passed to Google Gemini 3.5 Flash. The model writes an accurate, polite, and verified answer.

### Stage 3: Output Delivery (Synchronized Text & Cloned Speech)
* **Visual Output:** The text response streams onto the screen in real-time, complete with formatted lists, tables, bold text, and clickable source citations.
* **Audio Output:** In voice mode, the text is sent to the custom voice cloning engine (Fish Audio). The assistant speaks the answer aloud in a calm, natural human voice.
* **Turn-Taking Conversation:** While the AI is speaking through your speakers, the microphone is kept off so it never records its own voice. Once the AI finishes speaking, the microphone automatically opens again so you can immediately ask your next question without repeating any wake-word.
* **Instant Stop:** If you want to stop the assistant, simply say *"Stop"*, *"रुको"*, *"बस"*, or *"Bye Buddy"*, or click the button on screen.

---

## 📁 File-by-File Breakdown & Architecture

Here is what every individual file in this codebase does, what happens inside it, and its exact role in the overall system:

---

### 1. `main.py` — The Central Backend Server
* **What does it do?**
  It is the heart and brain of the entire application. It runs a high-performance web server built with FastAPI that coordinates the frontend, the vector database, the Gemini AI model, and the voice cloning engine.
* **What happens inside it?**
  * Serves the main website and web pages when someone visits the application URL.
  * Hosts the main question-and-answer API endpoint (`/ask`) which receives questions and streams back answers token-by-token.
  * Connects to the vector database to perform similarity searches and find matching document chunks.
  * Houses the custom Text-to-Speech API endpoint (`/tts`) that communicates with Fish Audio to generate realistic cloned voice audio for any sentence.
  * Provides endpoints to upload new PDF documents, retrieve chat conversation histories, and view indexed files.
  * Uses a lazy-loading proxy for embedding models so the server boots up in under 0.1 seconds on cloud deployments without freezing.
* **Output / Role:**
  Produces the live API and web server running on port 8000 or 10000, serving data and audio streams to the user interface.

---

### 2. `chat.html` — The Frontend User Interface
* **What does it do?**
  It is the complete visual interface that the user sees in the browser. It combines modern responsive design, real-time message streaming, and the voice assistant logic.
* **What happens inside it?**
  * Displays a dark-mode conversational UI with a sidebar for previous chats and indexed documents.
  * Features the **"Hello Buddy"** voice assistant panel that uses the Web Speech API to listen to the user's microphone.
  * Manages the conversational flow: pauses the microphone while the assistant is speaking through the laptop speakers to prevent echo loops, and turns the microphone back on as soon as the answer finishes.
  * Renders Markdown formatting, tables, source verification badges, and audio playback cards.
  * Supports drag-and-drop PDF uploads with live status indicators.
* **Output / Role:**
  The interactive web page rendered in Google Chrome, Microsoft Edge, or any modern web browser.

---

### 3. `ingest.py` — The Knowledge Base Ingestion Script
* **What does it do?**
  It is the batch processing utility that takes raw university syllabus books, marksheets, and notices from the `data/` folder and loads them into the cloud vector database.
* **What happens inside it?**
  * Scans the `data/` folder for PDF documents.
  * Calls `extractor.py` to extract all written text from each PDF.
  * Splits long documents into small, coherent paragraphs (chunks) using `chunker.py`.
  * Generates mathematical embeddings (384-dimensional vectors) for every chunk using FastEmbed ONNX.
  * Connects to the cloud PostgreSQL database and uploads the text along with its vector representation into the `knowledge_base` table.
* **Output / Role:**
  Populates the vector database so the AI has verified knowledge to reference when answering questions.

---

### 4. `extractor.py` — Intelligent PDF Text Extractor
* **What does it do?**
  It extracts readable text from PDF documents of all types, whether they are digital e-books or scanned marksheet photocopies.
* **What happens inside it?**
  * **Tier 1 (Digital Extraction):** First attempts to extract clean text using `pdfplumber`. For regular digital PDFs (like syllabus documents), this takes less than a second.
  * **Tier 2 (OCR Fallback):** If a PDF contains little to no digital text (for example, a scanned 10th marksheet or physical certificate), it automatically converts the pages into high-resolution images and uses Tesseract Optical Character Recognition (OCR) to read the printed words.
* **Output / Role:**
  Returns clean, raw text strings extracted from any uploaded or local PDF.

---

### 5. `chunker.py` — Semantic Document Chunker
* **What does it do?**
  Long documents cannot be processed as a single massive block. `chunker.py` divides large texts into small, bite-sized sections.
* **What happens inside it?**
  * Splits text into manageable segments (approximately 450 to 500 characters each).
  * Implements an overlap between consecutive chunks so that important sentences cut off at a boundary are not lost.
  * Preserves paragraph structure and heading context.
* **Output / Role:**
  Produces a list of structured text chunks ready to be converted into embeddings and stored in the database.

---

### 6. `database.py` — PostgreSQL & Vector Database Connector
* **What does it do?**
  Manages connections to the PostgreSQL database (hosted on Neon Cloud) and ensures the `pgvector` extension and required tables exist.
* **What happens inside it?**
  * Connects securely to the database using the connection string from environment variables.
  * Executes startup SQL commands to enable vector indexing (HNSW index) for rapid nearest-neighbor vector search.
  * Initializes the `knowledge_base` table with columns for document name, chunk text, page numbers, and vector embeddings.
* **Output / Role:**
  Provides a clean, reusable database connection to all other scripts in the application.

---

### 7. `memory_store.py` — Persistent Student Memory System
* **What does it do?**
  Gives the assistant long-term memory about the student. It ensures the assistant remembers facts across multiple conversations without needing to ask again.
* **What happens inside it?**
  * Stores key identity facts such as user's name, college name, branch, semester, and personal details in persistent JSON storage (`storage/memories.json`).
  * Provides functions to retrieve, update, and search memories.
  * Injects these personal facts into the AI's system prompt during every query so the assistant greets the user by name and tailors its advice to their specific branch and college.
* **Output / Role:**
  Provides personal context that makes the AI feel like a dedicated personal college tutor.

---

### 8. `threads_store.py` — Multi-Session Chat History
* **What does it do?**
  Manages conversation history so the user can switch between different chat sessions (like in ChatGPT) and review past answers.
* **What happens inside it?**
  * Saves and loads chat threads, timestamps, user questions, assistant answers, and cited sources.
  * Syncs conversation threads to cloud storage so chats persist even when the browser is refreshed or reopened on another device.
* **Output / Role:**
  Powers the sidebar chat history list in the user interface.

---

### 9. `Dockerfile` & Cloud Deployment Architecture
* **What does it do?**
  Packages the entire application—Python environment, Linux libraries, pre-cached ONNX embedding models, and server scripts—into an isolated, production-ready container for cloud deployment (e.g., Render, Docker).
* **What happens inside it?**
  * Uses a minimal Linux Python base image.
  * Installs required system dependencies (PostgreSQL client libraries, curl, build essentials).
  * Pre-downloads and permanently bakes the FastEmbed ONNX model directly into the image (`/app/fastembed_cache`) during build time, ensuring the cloud server starts in under 3 minutes without waiting for external model downloads.
* **Output / Role:**
  Enables 24/7 one-click cloud hosting on free-tier platforms with $0.00 infrastructure cost.

---

## 🎙️ The Voice Assistant Engine: How "Hello Buddy" Operates

The voice assistant was designed to feel natural and effortless while avoiding common voice AI pitfalls (like audio feedback loops). Here is how the voice state machine works:

1. **Explicit Activation:**
   The microphone is completely dormant when the page opens. It only begins listening when the user clicks the **"Hello Buddy"** button in the header.
2. **Speech Recognition:**
   The Web Speech API listens for spoken queries in English and Hindi/Hinglish. It detects when the speaker stops talking and submits the question.
3. **Acoustic Echo Prevention:**
   While the AI generates and speaks the answer, the microphone is automatically stopped. This ensures the microphone never hears the sound coming out of the laptop speakers, completely eliminating infinite self-reinforcing echo loops.
4. **Natural Continuation:**
   The moment the audio playback ends, the microphone automatically starts listening again. You can ask follow-up questions seamlessly without clicking anything again.
5. **Clean Exit:**
   Saying *"Stop"*, *"रुको"*, *"बस"*, or *"Bye Buddy"*, or clicking the button on screen, instantly silences the voice and closes the assistant.

---

## 💡 How to Explain This Project (Summary for Interviews & Presentations)

> *"I built an intelligent College Assistant using Retrieval-Augmented Generation (RAG) and Custom Voice Cloning. The application solves AI hallucinations by grounding all answers in verified syllabus books, academic notices, and marksheets stored in a Neon PostgreSQL vector database using pgvector. The system features a FastAPI backend, Gemini 3.5 Flash for grounded reasoning, and an integrated 'Hello Buddy' voice assistant that speaks using a realistic cloned human voice via Fish Audio. The entire architecture is containerized with Docker and deployed to the cloud at zero hosting cost."*
