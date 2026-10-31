import os
import ollama  # Naya import
from database import get_db_connection, init_db
from extractor import extract_text_hybrid
from chunker import chunk_text

from sentence_transformers import SentenceTransformer

if __name__ == "__main__":
    print("Starting document ingestion process...\n")
    
    # 1. Setup Database
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    print("Loading embedding model (all-MiniLM-L6-v2)...")
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    data_folder = "data"
    
    if not os.path.exists(data_folder):
        print(f"Error: The folder '{data_folder}' does not exist.")
    else:
        # 2. Loop through all PDFs
        for filename in os.listdir(data_folder):
            if filename.lower().endswith(".pdf"):
                pdf_file = os.path.join(data_folder, filename)
                print(f"Processing {filename}...")
                
                # Extract
                raw_text = extract_text_hybrid(pdf_file)
                
                # Chunk
                chunks = chunk_text(raw_text, chunk_size=150)
                print(f" -> Split into {len(chunks)} chunks. Generating embeddings...")
                
                # Store in Postgres with Embeddings
                for chunk in chunks:
                    embedding_vector = embedding_model.encode(chunk).tolist()
                    
                    cursor.execute(
                        "INSERT INTO college_docs (filename, chunk_text, embedding) VALUES (%s, %s, %s)",
                        (filename, chunk, embedding_vector)
                    )
                # ------------------------------
                
                conn.commit()
                print(f"[SUCCESS] Saved {filename} with vectors to database.\n")

    cursor.close()
    conn.close()
    print("All documents processed and stored in Postgres!")