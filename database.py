import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    # 1. Cloud-managed connection string (Neon, Supabase, Railway, Render)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    # 2. Individual environment variables or local fallback
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "rag_db"), 
        user=os.getenv("DB_USER", "admin"), 
        password=os.getenv("DB_PASSWORD", "password"), 
        host=os.getenv("DB_HOST", "localhost"), 
        port=int(os.getenv("DB_PORT", 5432))
    )

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # 1. Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS college_docs (
                id SERIAL PRIMARY KEY,
                filename TEXT,
                chunk_text TEXT,
                embedding vector
            );
        """)

        # 2. User memories & learned facts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_memories (
                id SERIAL PRIMARY KEY,
                category TEXT DEFAULT 'general',
                key_topic TEXT UNIQUE,
                memory_text TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] Database and tables initialized successfully.")
    except Exception as e:
        print(f"[DB Notice] PostgreSQL initialization skipped or failed ({e}). Persistent storage uses local JSON storage.")
