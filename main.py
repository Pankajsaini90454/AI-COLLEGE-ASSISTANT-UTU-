from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, Response
from pydantic import BaseModel
import os
import shutil
import json
import re
import httpx
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

from database import get_db_connection, init_db
from extractor import extract_text_hybrid
from chunker import chunk_text
import memory_store
import threads_store

# 1. Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# 2. Configure Gemini
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[Gemini Config Notice] {e}")

# 3. Load lightweight embedding model (FastEmbed ONNX - Memory: ~75MB for 512MB RAM cloud tiers)
def to_vector(emb):
    if hasattr(emb, "tolist"):
        return [float(x) for x in emb.tolist()]
    if isinstance(emb, list):
        return [float(x) for x in emb]
    return [float(x) for x in list(emb)]


class LightweightEmbedder:
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        cache_path = os.getenv("FASTEMBED_CACHE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fastembed_cache"))
        os.makedirs(cache_path, exist_ok=True)
        try:
            from fastembed import TextEmbedding
            print(f"[Embedding Engine] Initializing FastEmbed (ONNX, ultra-lightweight) with cache_dir={cache_path}...")
            self._backend = "fastembed"
            self._model = TextEmbedding(model_name=model_name, cache_dir=cache_path)
            print("[Embedding Engine] FastEmbed loaded successfully!")
        except Exception as e:
            print(f"[Embedding Engine] Fallback to SentenceTransformer: {e}")
            from sentence_transformers import SentenceTransformer
            self._backend = "sentence_transformers"
            self._model = SentenceTransformer(model_name.replace("sentence-transformers/", ""))

    def encode(self, text):
        if self._backend == "fastembed":
            if isinstance(text, str):
                return [float(x) for x in list(self._model.embed([text]))[0]]
            return [[float(x) for x in emb] for emb in self._model.embed(text)]
        else:
            res = self._model.encode(text)
            return to_vector(res)

    def get_embedding_dimension(self):
        return 384


# Lazy-loaded singleton proxy so Uvicorn starts instantly without blocking on model download
_embedding_model_instance = None

def get_embedding_model():
    global _embedding_model_instance
    if _embedding_model_instance is None:
        _embedding_model_instance = LightweightEmbedder()
    return _embedding_model_instance

class LazyEmbeddingModelProxy:
    def __getattr__(self, name):
        return getattr(get_embedding_model(), name)

embedding_model = LazyEmbeddingModelProxy()

app = FastAPI(title="AI College Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class QuestionRequest(BaseModel):
    question: str
    thread_id: str | None = None
    history: list[ChatHistoryMessage] = []


class ThreadSaveRequest(BaseModel):
    id: str
    title: str = "New Conversation"
    messages: list[dict] = []


def ensure_embedding_dimensions():
    try:
        init_db()
        dimension = embedding_model.get_embedding_dimension()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, chunk_text
            FROM college_docs
            WHERE embedding IS NULL OR vector_dims(embedding) <> %s
            """,
            (dimension,)
        )
        outdated_chunks = cursor.fetchall()

        for chunk_id, chunk_text in outdated_chunks:
            embedding_vector = to_vector(embedding_model.encode(chunk_text))
            cursor.execute(
                "UPDATE college_docs SET embedding = %s WHERE id = %s",
                (embedding_vector, chunk_id)
            )

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB Notice] ensure_embedding_dimensions skipped or failed: {e}")


# ================= HTTP ROUTES =================

@app.get("/")
@app.get("/chat")
def serve_chat():
    if os.path.exists("chat.html"):
        return FileResponse("chat.html")
    return {"status": "Success", "message": "FastAPI is running!"}


# --- THREAD PERSISTENCE ENDPOINTS ---

@app.get("/api/threads")
def list_threads():
    """Retrieve all saved threads from persistent server storage."""
    return {"threads": threads_store.get_all_threads()}


@app.post("/api/threads")
def save_thread(payload: ThreadSaveRequest):
    """Save or update an entire thread on disk."""
    success = threads_store.save_or_update_thread(payload.model_dump())
    return {"status": "Success" if success else "Error"}


@app.delete("/api/threads/{thread_id}")
def delete_thread_endpoint(thread_id: str):
    """Delete a specific thread."""
    success = threads_store.delete_thread(thread_id)
    return {"status": "Success" if success else "Error"}


@app.delete("/api/threads")
def clear_all_threads_endpoint():
    """Clear all threads."""
    success = threads_store.clear_all_threads()
    return {"status": "Success" if success else "Error"}


# --- MEMORY PERSISTENCE ENDPOINTS ---

@app.get("/api/memories")
def list_memories():
    """List all active persistent memories."""
    return {"memories": memory_store.get_all_memories()}


@app.delete("/api/memories/{key}")
def delete_memory_endpoint(key: str):
    """Delete a specific memory."""
    success = memory_store.delete_memory(key)
    return {"status": "Success" if success else "Error"}


@app.delete("/api/memories")
def clear_memories_endpoint():
    """Clear all stored memories."""
    success = memory_store.clear_all_memories()
    return {"status": "Success" if success else "Error"}


# --- PDF INGESTION & DOCUMENT ENDPOINTS ---

@app.get("/api/documents")
def list_documents():
    """Retrieve list of unique documents currently indexed in pgvector."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT filename, COUNT(*) as chunks_count
            FROM college_docs
            GROUP BY filename
            ORDER BY filename ASC;
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"documents": [{"filename": r[0] or "General Document", "chunks": r[1]} for r in rows]}
    except Exception as e:
        return {"documents": []}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        if not os.path.exists("data"):
            os.makedirs("data", exist_ok=True)
        file_location = f"data/{file.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)

        raw_text = extract_text_hybrid(file_location)
        if not raw_text.strip():
            return {"status": "Error", "message": f"No readable text found in {file.filename}."}

        chunks = chunk_text(raw_text, chunk_size=150)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM college_docs WHERE filename = %s", (file.filename,))
        conn.commit()

        from psycopg2.extras import execute_values
        records = []
        for chunk in chunks:
            emb = to_vector(embedding_model.encode(chunk))
            records.append((file.filename, chunk, emb))

        execute_values(
            cursor,
            "INSERT INTO college_docs (filename, chunk_text, embedding) VALUES %s",
            records
        )
        conn.commit()
        cursor.close()
        conn.close()

        return {"status": "Success", "message": f"{file.filename} uploaded and processed ({len(chunks)} chunks)!"}
    except Exception as e:
        print(f"[Upload Error] {e}")
        return {"status": "Error", "message": str(e)}


# --- ASK ASSISTANT (RAG + MEMORY + STREAMING) ---

@app.post("/ask")
def ask_assistant(request: QuestionRequest):
    user_question = request.question.strip()
    current_year = datetime.now().year

    # Check for API Key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_KEY")
    if not api_key:
        def missing_key_stream():
            err_msg = "Gemini API key is missing on the server. Please add GEMINI_API_KEY in your Render dashboard under the 'Environment' tab."
            yield f"data: {json.dumps({'error': err_msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            missing_key_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    try:
        genai.configure(api_key=api_key)
        primary_model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        fallback_model_name = "gemini-3.8-flash"

        # 1. EXTRACT & UPDATE PERSISTENT MEMORIES
        # Rule-based detection (zero latency, zero API calls)
        memory_store.extract_and_save_memories(user_question)

        # 2. RETRIEVE RELEVANT DOCUMENT CHUNKS FROM VECTOR DATABASE
        context = ""
        sources_metadata = []
        try:
            question_embedding = to_vector(embedding_model.encode(user_question))
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chunk_text, filename, (1 - (embedding <=> %s::vector)) AS similarity
                FROM college_docs
                ORDER BY embedding <=> %s::vector
                LIMIT 8;
            """, (question_embedding, question_embedding))
            results = list(cursor.fetchall())

            # Student Profile & Course Booster: Ensure personal/course chunks are included for relevant queries
            q_lower = user_question.lower()
            personal_keywords = ["name", "who am i", "my roll", "profile", "cv", "resume", "10th", "12th", "marks", "score", "grade", "gpa", "cgpa", "pankaj", "data science", "syllabus", "calendar", "holiday", "college", "institute", "bias", "bhimtal", "university", "located", "where", "study"]
            if any(k in q_lower for k in personal_keywords):
                target_files = []
                if any(k in q_lower for k in ["name", "who am i", "profile", "cv", "resume", "pankaj", "college", "institute", "bias", "bhimtal", "university", "located", "where", "study"]):
                    target_files.extend(["Pankaj_CV.pdf", "The_Ultimate_Job_Ready_Data_Science_Course_Certificate.pdf"])
                if any(k in q_lower for k in ["10th", "12th", "marks", "score", "grade", "gpa"]):
                    target_files.extend(["12th.pdf", "10th.pdf"])
                if "data science" in q_lower:
                    target_files.extend(["data_science_notes.pdf", "The_Ultimate_Job_Ready_Data_Science_Course_Certificate.pdf"])
                if any(k in q_lower for k in ["calendar", "holiday", "vacation"]):
                    target_files.extend(["639222394440338142.pdf"])

                if target_files:
                    cursor.execute("""
                        SELECT chunk_text, filename, 0.95 as similarity
                        FROM college_docs
                        WHERE filename = ANY(%s)
                        ORDER BY id ASC
                        LIMIT 4;
                    """, (target_files,))
                    boosted = cursor.fetchall()
                    existing_texts = {r[0] for r in results}
                    for b in boosted:
                        if b[0] not in existing_texts:
                            results.insert(0, b)

            cursor.close()
            conn.close()

            context_chunks = []
            seen_files = set()
            for row in results[:10]:
                chunk_text = row[0]
                fname = row[1] if len(row) > 1 and row[1] else "College Document"
                sim_score = float(row[2]) if len(row) > 2 and row[2] is not None else 0.85
                context_chunks.append(f"[{fname}]\n{chunk_text}")

                if fname not in seen_files:
                    seen_files.add(fname)
                    pct = max(60, min(99, int(sim_score * 100))) if sim_score < 1.0 else 96
                    snippet = " ".join(chunk_text.split())[:130] + "..."
                    sources_metadata.append({
                        "filename": fname,
                        "match": f"{pct}% match",
                        "snippet": snippet
                    })

            context = "\n\n".join(context_chunks)
        except Exception as db_err:
            print(f"[Vector Search Notice] Could not retrieve DB chunks: {db_err}")
            context = "No document database chunks available at this moment."

        # 3. GET ALL PERSISTENT STORED MEMORIES
        formatted_memories = memory_store.format_memories_for_prompt()

        # 4. FORMAT CONVERSATION HISTORY
        history_lines = []
        for h in request.history[-10:]:
            role_label = "Student" if h.role == "user" else "College AI"
            history_lines.append(f"{role_label}: {h.content}")
        formatted_history = "\n".join(history_lines) if history_lines else "None (New conversation)"

        # 5. CONSTRUCT SYSTEM PROMPT (STRICT: NO ROBOTIC DISCLAIMERS + USER MEMORY OVERRIDE)
        system_prompt = f"""You are a helpful, professional, and friendly College AI Assistant.
The current year is {current_year}.

=================== ABSOLUTE RULES ON TONE & STYLE (MANDATORY) ===================
1. NEVER USE META-DISCLAIMERS OR ROBOTIC FILLER:
   - STRICTLY FORBIDDEN PHRASES:
     ❌ "Based on your provided document..."
     ❌ "According to the uploaded files..."
     ❌ "As per the documents provided..."
     ❌ "Based on the context..."
     ❌ "From the marksheet/PDF..."
     ❌ "Okay [Name], but based on your provided document..."
   - ALWAYS state answers DIRECTLY, naturally, and concisely as a knowledgeable assistant.
   
   Examples:
   - Question: "What is my name?"
     CORRECT: "Your name is Rahul." (or "Your name is Pankaj Saini.")
     WRONG: "Based on your provided document, your name is..."
     
   - Question: "What's my marks in 12th?"
     CORRECT: "Your marks are 484 out of 500."
     WRONG: "Based on your provided document, your marks is 484..."
     
   - User correction: "My name is Rahul"
     CORRECT: "Okay Rahul! I'll remember that."
     WRONG: "Okay Rahul, but according to your document it says Pankaj Saini."

2. USER MEMORIES & CORRECTIONS OVERRIDE ALL DOCUMENTS (TOP PRIORITY):
   - Whatever the student tells you about themselves (name, roll number, course, corrections) is the ABSOLUTE TRUTH.
   - If a document says one name (e.g., Pankaj Saini) but user memory or conversation says another name (e.g., Rahul), Rahul is their true name. NEVER question it or cite the old name.
   - If the student tells you an extra subject for a semester (e.g. "Cloud Computing is also in 3rd semester"), ADD IT to the official syllabus when listing subjects.

3. DIRECT AND CRISP ANSWERS:
   - Answer accurately and directly without unnecessary preamble or fluff.
   - For simple personal or factual questions (e.g. name, college name, campus location, marks), provide a direct, concise 1-2 sentence response so voice replies are lightning fast and clear.
   - When code is requested, output clean code in standard markdown code blocks with the language identifier (e.g. ```cpp).
==================================================================================

=== STORED USER MEMORIES & LEARNED FACTS (HIGHEST PRIORITY) ===
{formatted_memories}
===============================================================

=== RETRIEVED CONTEXT FROM COLLEGE DOCUMENTS ===
{context}
================================================

=== RECENT CONVERSATION HISTORY ===
{formatted_history}
==================================

Student's Latest Message: {user_question}
"""

        # 6. STREAM GENERATION & AUTO-PERSISTENCE
        def stream_response():
            full_response_text = ""
            active_model = None
            try:
                try:
                    active_model = genai.GenerativeModel(primary_model_name)
                    response = active_model.generate_content(system_prompt, stream=True)
                except Exception:
                    active_model = genai.GenerativeModel(fallback_model_name)
                    response = active_model.generate_content(system_prompt, stream=True)

                for chunk in response:
                    text_val = ""
                    try:
                        text_val = chunk.text
                    except Exception:
                        pass
                    if text_val:
                        full_response_text += text_val
                        yield f"data: {json.dumps({'text': text_val})}\n\n"

            except Exception as stream_err:
                print(f"[Streaming Warning] {stream_err}. Attempting direct generation fallback...")

            # If streaming produced empty output, fallback to direct non-streaming generation
            if not full_response_text:
                try:
                    direct_model = active_model or genai.GenerativeModel(primary_model_name)
                    res = direct_model.generate_content(system_prompt)
                    if res.text:
                        full_response_text = res.text
                        yield f"data: {json.dumps({'text': full_response_text})}\n\n"
                except Exception as direct_err:
                    try:
                        fallback_model = genai.GenerativeModel(fallback_model_name)
                        res = fallback_model.generate_content(system_prompt)
                        if res.text:
                            full_response_text = res.text
                            yield f"data: {json.dumps({'text': full_response_text})}\n\n"
                    except Exception as final_err:
                        yield f"data: {json.dumps({'error': str(final_err)})}\n\n"

            # Send grounding sources metadata before closing stream
            if sources_metadata:
                yield f"data: {json.dumps({'sources': sources_metadata})}\n\n"

            yield "data: [DONE]\n\n"

            # Persist to disk thread storage immediately
            if request.thread_id and full_response_text:
                time_str = datetime.now().strftime("%I:%M %p")
                threads_store.append_message_to_thread(request.thread_id, "user", user_question, time_str)
                threads_store.append_message_to_thread(
                    request.thread_id,
                    "assistant",
                    full_response_text,
                    time_str,
                    sources=sources_metadata
                )

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- CUSTOM CLONED VOICE TTS (FISH AUDIO MULTILINGUAL) ---
class TTSRequest(BaseModel):
    text: str

@app.post("/tts")
async def generate_cloned_tts(request: TTSRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    api_key = os.getenv("FISH_AUDIO_API_KEY", "sk-fish-uZFISpcxIwwKBFQX_9ni3LpEqKzkm7K62fuvXI6x4TM")
    voice_id = os.getenv("FISH_AUDIO_VOICE_ID", "9e338294a69a49f78c1c9f03f7bb2802")

    # Clean text: remove markdown artifacts, code snippets, URLs, brackets
    cleaned = re.sub(r'```[\s\S]*?```', '', text)
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    cleaned = re.sub(r'\[.*?\]', '', cleaned)
    cleaned = re.sub(r'[*_~#>`\(\)]', '', cleaned)
    cleaned = re.sub(r'[-–—]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if not cleaned:
        cleaned = text[:200]

    url = "https://api.fish.audio/v1/tts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": "s2.1-pro-free"
    }
    payload = {
        "text": cleaned,
        "reference_id": voice_id,
        "format": "mp3",
        "normalize": True,
        "temperature": 0.7,
        "latency": "balanced",
        "prosody": {
            "speed": 1.05,
            "volume": 0.0
        }
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return Response(content=resp.content, media_type="audio/mpeg")
            else:
                print(f"[Fish Audio Error] status={resp.status_code} text={resp.text[:250]}")
                raise HTTPException(status_code=resp.status_code, detail=f"TTS generation error ({resp.status_code})")
        except Exception as e:
            print(f"[Fish Audio Exception] {e}")
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
