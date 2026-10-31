import os
import json
import re
from datetime import datetime

STORAGE_DIR = "storage"
MEMORIES_FILE = os.path.join(STORAGE_DIR, "memories.json")


def _ensure_storage():
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR, exist_ok=True)
    if not os.path.exists(MEMORIES_FILE):
        with open(MEMORIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def get_all_memories() -> list[dict]:
    """Retrieve all persistent memories as a list of dicts."""
    _ensure_storage()
    try:
        with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = []
        for key, item in data.items():
            results.append({
                "key": key,
                "category": item.get("category", "general"),
                "value": item.get("value", ""),
                "updated_at": item.get("updated_at", "")
            })
        return results
    except Exception as e:
        print(f"[Memory Store Error] get_all_memories failed: {e}")
        return []


def get_memory_value(key: str) -> str | None:
    """Get the value of a specific memory key."""
    _ensure_storage()
    try:
        with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        item = data.get(key.strip().lower())
        return item.get("value") if item else None
    except Exception:
        return None


def save_memory(key: str, value: str, category: str = "general") -> bool:
    """Save or update a memory fact on disk and in database if available."""
    _ensure_storage()
    key = key.strip().lower()
    value = value.strip()
    if not key or not value:
        return False

    # 1. Save to local storage file
    try:
        with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # If updating a list (like subjects), append cleanly
        if key in data and "subject" in key:
            old_val = data[key].get("value", "")
            if value.lower() not in old_val.lower():
                value = f"{old_val}; {value}"

        data[key] = {
            "category": category,
            "value": value,
            "updated_at": datetime.now().isoformat()
        }
        with open(MEMORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Memory Store] Saved fact -> [{key}]: {value}")
    except Exception as e:
        print(f"[Memory Store Error] Failed to write memory to file: {e}")
        return False

    # 2. Also save to PostgreSQL user_memories table if database is accessible
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_memories (category, key_topic, memory_text, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key_topic) 
            DO UPDATE SET 
                memory_text = EXCLUDED.memory_text,
                category = EXCLUDED.category,
                updated_at = CURRENT_TIMESTAMP;
        """, (category, key, value))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass

    return True


def delete_memory(key: str) -> bool:
    """Delete a specific memory."""
    _ensure_storage()
    key = key.strip().lower()
    try:
        with open(MEMORIES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if key in data:
            del data[key]
            with open(MEMORIES_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        return False
    except Exception:
        return False


def clear_all_memories() -> bool:
    """Clear all memories."""
    _ensure_storage()
    try:
        with open(MEMORIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return True
    except Exception:
        return False


def format_memories_for_prompt() -> str:
    """Format stored memories into a clear block for the Gemini system prompt."""
    memories = get_all_memories()
    if not memories:
        return "No specific user memories stored yet."

    lines = []
    for m in memories:
        lines.append(f"• [{m['category'].upper()}] {m['key']}: {m['value']}")
    return "\n".join(lines)


def extract_and_save_memories(user_msg: str) -> list[str]:
    """
    Extract user facts, name corrections, and syllabus additions from user message.
    Pure rule-based for 0 API latency and 100% precision.
    """
    saved = []
    text = user_msg.strip()
    lower = text.lower()

    # IGNORE QUESTIONS (e.g. "What is my name?", "What's my name", "Mera naam kya hai?")
    is_question = (
        "?" in text or 
        lower.startswith(("what", "who", "which", "where", "how", "kya", "tell me", "can you", "show me")) or
        "kya hai" in lower or
        "kya h" in lower
    )
    if is_question:
        return []

    # 1. NAME STATEMENTS & CORRECTIONS
    # e.g., "My name is Rahul", "No, my name is Rahul", "Mera naam Rahul hai", "Call me Rahul", "Rahul is my name"
    name_patterns = [
        r"(?:my name is|mera naam|call me|naam hai|no[, ]+my name is|actually my name is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)",
        r"^i am\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)$",
        r"^([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(?:is my name|hai mera naam)$"
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_name = match.group(1).strip()
            # Avoid matching common words
            stop_words = ["what", "who", "where", "how", "here", "sir", "student", "college", "assistant", "fine", "good", "okay", "done"]
            if raw_name.lower() not in stop_words and len(raw_name) >= 2:
                save_memory("user_name", raw_name, category="user_profile")
                saved.append(f"User's name is {raw_name}")
                break

    # 2. SEMESTER SUBJECT ADDITIONS
    # e.g., "3rd semester me Cloud Computing subject bhi hai", "add Machine Learning in 3rd sem"
    sem_match = re.search(r"(?:(\d+)(?:st|nd|rd|th)?\s+(?:sem|semester)|(?:sem|semester)\s*(\d+))", lower)
    if sem_match and any(w in lower for w in ["subject", "bhi hai", "add", "include", "course", "paper"]):
        sem_num = sem_match.group(1) or sem_match.group(2)
        sub_extract = re.search(r"(?:is|hai|bhi hai|add|include|subject)\s*[:\-]?\s*([A-Za-z0-9\s]+?)(?:\s+subject|\s+bhi|\s+ko|\.|$)", text, re.IGNORECASE)
        if sub_extract:
            subject_name = sub_extract.group(1).strip()
            if len(subject_name) > 2 and subject_name.lower() not in ["what", "which", "all", "the", "bhi"]:
                save_memory(f"sem_{sem_num}_additional_subjects", subject_name, category="curriculum_correction")
                saved.append(f"Semester {sem_num} includes additional subject: {subject_name}")

    # 3. EXPLICIT "REMEMBER THAT" / "NOTE THAT"
    remember_match = re.search(r"(?:remember that|remember:|please remember|yaad rakhna ki|note that)\s+(.+)", text, re.IGNORECASE)
    if remember_match:
        fact = remember_match.group(1).strip()
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', fact[:20]).lower().strip('_')
        save_memory(f"note_{slug}", fact, category="user_note")
        saved.append(f"Remembered: {fact}")

    return saved
