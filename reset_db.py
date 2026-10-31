from database import get_db_connection

try:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # This command deletes all data from the old table
    cursor.execute("TRUNCATE TABLE college_docs;")
    conn.commit()
    
    cursor.close()
    conn.close()
    print("✅ Database successfully cleared! Now you can upload PDFs with Gemini.")
    
except Exception as e:
    print(f"❌ Error: {e}")