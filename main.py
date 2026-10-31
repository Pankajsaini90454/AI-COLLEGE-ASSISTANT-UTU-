from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import os
import shutil
import json
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# 2. Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 3. Load lightweight embedding model (FastEmbed ONNX - Memory: ~75MB for 512MB RAM cloud tiers)
class LightweightEmbedder:
    def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from fastembed import TextEmbedding
            print("[Embedding Engine] Initializing FastEmbed (ONNX, ultra-lightweight)...")
            self._backend = "fastembed"
            self._model = TextEmbedding(model_name=model_name)
        except Exception as e:
            print(f"[Embedding Engine] Fallback to SentenceTransformer: {e}")
            from sentence_transformers import SentenceTransformer
            self._backend = "sentence_transformers"
            self._model = SentenceTransformer(model_name.replace("sentence-transformers/", ""))

    def encode(self, text):
        if self._backend == "fastembed":
            if isinstance(text, str):
                return list(self._model.embed([text]))[0].tolist()
            return [x.tolist() for x in self._model.embed(text)]
        else:
            return self._model.encode(text)

    def get_embedding_dimension(self):
        return 384

print("Loading embedding model...")
embedding_model = LightweightEmbedder()
print("Embedding model loaded successfully!")

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
            embedding_vector = embedding_model.encode(chunk_text).tolist()
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
def health_check():
    return {"status": "Success", "message": "FastAPI is running!"}


@app.get("/chat")
def serve_chat():
    if os.path.exists("chat.html"):
        return FileResponse("chat.html")
    raise HTTPException(status_code=404, detail="chat.html not found")


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
        chunks = chunk_text(raw_text, chunk_size=150)

        ensure_embedding_dimensions()
        conn = get_db_connection()
        cursor = conn.cursor()
        for chunk in chunks:
            embedding_vector = embedding_model.encode(chunk).tolist()
            cursor.execute(
                "INSERT INTO college_docs (filename, chunk_text, embedding) VALUES (%s, %s, %s)",
                (file.filename, chunk, embedding_vector)
            )
        conn.commit()
        cursor.close()
        conn.close()

        return {"status": "Success", "message": f"{file.filename} uploaded and processed!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- ASK ASSISTANT (RAG + MEMORY + STREAMING) ---

@app.post("/ask")
def ask_assistant(request: QuestionRequest):
    user_question = request.question.strip()
    current_year = datetime.now().year

    try:
        primary_model_name = GEMINI_MODEL_NAME
        fallback_model_name = "gemini-3.1-flash-lite"

        # 1. EXTRACT & UPDATE PERSISTENT MEMORIES
        # Rule-based detection (zero latency, zero API calls)
        memory_store.extract_and_save_memories(user_question)

        # 2. RETRIEVE RELEVANT DOCUMENT CHUNKS FROM VECTOR DATABASE
        context = ""
        sources_metadata = []
        try:
            ensure_embedding_dimensions()
            question_embedding = embedding_model.encode(user_question).tolist()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chunk_text, filename, (1 - (embedding <=> %s::vector)) AS similarity
                FROM college_docs
                ORDER BY embedding <=> %s::vector
                LIMIT 8;
            """, (question_embedding, question_embedding))
            results = cursor.fetchall()
            cursor.close()
            conn.close()

            context_chunks = []
            seen_files = set()
            for row in results:
                chunk_text = row[0]
                fname = row[1] if len(row) > 1 and row[1] else "College Document"
                sim_score = float(row[2]) if len(row) > 2 and row[2] is not None else 0.85
                context_chunks.append(chunk_text)

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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
