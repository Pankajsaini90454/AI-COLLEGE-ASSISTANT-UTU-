from database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

print("Dropping restricted table...")
cursor.execute("DROP TABLE IF EXISTS college_docs;")

print("Creating flexible table with no dimension limits...")
# Notice we just use 'vector' without a number
cursor.execute("""
CREATE TABLE college_docs (
    id SERIAL PRIMARY KEY,
    filename TEXT,
    chunk_text TEXT,
    embedding vector
);
""")

conn.commit()
cursor.close()
conn.close()
print("✅ Database reset and is now fully flexible!")