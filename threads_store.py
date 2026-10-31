import os
import json
import time

STORAGE_DIR = "storage"
THREADS_FILE = os.path.join(STORAGE_DIR, "threads.json")


def _ensure_storage():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(THREADS_FILE):
        with open(THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def get_all_threads() -> list[dict]:
    """Retrieve all saved chat threads from persistent storage."""
    _ensure_storage()
    try:
        with open(THREADS_FILE, "r", encoding="utf-8") as f:
            threads = json.load(f)
        # Sort by updated_at desc
        threads.sort(key=lambda t: t.get("updated_at", 0), reverse=True)
        return threads
    except Exception as e:
        print(f"[Threads Store Error] Failed to read threads: {e}")
        return []


def get_thread(thread_id: str) -> dict | None:
    """Get a specific thread by ID."""
    threads = get_all_threads()
    for t in threads:
        if t.get("id") == thread_id:
            return t
    return None


def save_or_update_thread(thread_data: dict) -> bool:
    """Save or update an entire thread object."""
    _ensure_storage()
    thread_id = thread_data.get("id")
    if not thread_id:
        return False

    try:
        with open(THREADS_FILE, "r", encoding="utf-8") as f:
            threads = json.load(f)

        found = False
        now_ts = int(time.time() * 1000)
        for idx, t in enumerate(threads):
            if t.get("id") == thread_id:
                threads[idx]["title"] = thread_data.get("title", t.get("title", "Conversation"))
                threads[idx]["messages"] = thread_data.get("messages", t.get("messages", []))
                threads[idx]["updated_at"] = now_ts
                found = True
                break

        if not found:
            thread_data["updated_at"] = now_ts
            if "created_at" not in thread_data:
                thread_data["created_at"] = now_ts
            threads.insert(0, thread_data)

        with open(THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump(threads, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Threads Store Error] save_or_update_thread failed: {e}")
        return False


def append_message_to_thread(thread_id: str, role: str, content: str, time_str: str = "", sources: list | None = None) -> dict:
    """Append a single message to a thread and persist immediately."""
    _ensure_storage()
    now_ts = int(time.time() * 1000)

    try:
        with open(THREADS_FILE, "r", encoding="utf-8") as f:
            threads = json.load(f)
    except Exception:
        threads = []

    target_thread = None
    for t in threads:
        if t.get("id") == thread_id:
            target_thread = t
            break

    if not target_thread:
        # Create new thread on the fly
        target_thread = {
            "id": thread_id,
            "title": content[:30] if role == "user" else "New Conversation",
            "created_at": now_ts,
            "updated_at": now_ts,
            "messages": []
        }
        threads.insert(0, target_thread)

    # Auto title if it's the first user question
    if role == "user" and (target_thread.get("title") in ["New Conversation", "Current Conversation", "New Chat", ""]):
        clean_title = content.strip().replace("\n", " ")
        target_thread["title"] = clean_title[:32] + ("..." if len(clean_title) > 32 else "")

    new_msg = {
        "role": role,
        "content": content,
        "time": time_str
    }
    if sources:
        new_msg["sources"] = sources

    target_thread["messages"].append(new_msg)
    target_thread["updated_at"] = now_ts

    try:
        with open(THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump(threads, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Threads Store Error] append_message_to_thread failed: {e}")

    return target_thread


def delete_thread(thread_id: str) -> bool:
    """Delete a thread by ID."""
    _ensure_storage()
    try:
        with open(THREADS_FILE, "r", encoding="utf-8") as f:
            threads = json.load(f)
        threads = [t for t in threads if t.get("id") != thread_id]
        with open(THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump(threads, f, indent=2)
        return True
    except Exception:
        return False


def clear_all_threads() -> bool:
    """Clear all threads."""
    _ensure_storage()
    try:
        with open(THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return True
    except Exception:
        return False
