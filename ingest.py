import os
import time
from database import get_db_connection, init_db
from extractor import extract_text_hybrid
from chunker import chunk_text
from psycopg2.extras import execute_values

try:
    from fastembed import TextEmbedding

    class LightweightEmbedder:
        def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2"):
            self._model = TextEmbedding(model_name=model_name)

        def encode_batch(self, texts, batch_size=64):
            embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embs = list(self._model.embed(batch))
                embeddings.extend([[float(x) for x in emb] for emb in batch_embs])
            return embeddings

    embedding_model = LightweightEmbedder()
except Exception:
    from sentence_transformers import SentenceTransformer

    class SentenceTransformerWrapper:
        def __init__(self, model_name="all-MiniLM-L6-v2"):
            self._model = SentenceTransformer(model_name)

        def encode_batch(self, texts, batch_size=64):
            embs = self._model.encode(texts, batch_size=batch_size, show_progress_bar=False)
            return [[float(x) for x in emb] for emb in embs]

    embedding_model = SentenceTransformerWrapper()


if __name__ == "__main__":
    print("=" * 60)
    print("AI College Assistant: Knowledge Base Ingestion to Neon DB")
    print("=" * 60)

    # 1. Setup Database
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    data_folder = "data"

    if not os.path.exists(data_folder):
        print(f"[Error] The folder '{data_folder}' does not exist.")
    else:
        # 2. Loop through all PDFs
        pdf_files = sorted([f for f in os.listdir(data_folder) if f.lower().endswith(".pdf")])
        print(f"Found {len(pdf_files)} PDF documents in '{data_folder}/':")
        for f in pdf_files:
            print(f" - {f}")
        print("\nStarting indexing...\n")

        total_inserted = 0
        overall_start = time.time()

        for filename in pdf_files:
            pdf_file = os.path.join(data_folder, filename)
            t0 = time.time()
            print(f"[{filename}]")
            print("  -> Extracting text...")
            raw_text = extract_text_hybrid(pdf_file)

            if not raw_text.strip():
                print(f"  -> [Warning] No text extracted from {filename}. Skipping.\n")
                continue

            # Clean old chunks of this file to prevent duplicates
            cursor.execute("DELETE FROM college_docs WHERE filename = %s", (filename,))
            conn.commit()

            # Chunk
            chunks = chunk_text(raw_text, chunk_size=150)
            print(f"  -> Extracted {len(raw_text):,} chars. Split into {len(chunks)} chunks.")

            # Batch Embedding
            print(f"  -> Generating {len(chunks)} vector embeddings...")
            embeddings = embedding_model.encode_batch(chunks, batch_size=64)

            # Fast Batch Insertion into Neon PostgreSQL
            records = [(filename, c, emb) for c, emb in zip(chunks, embeddings)]
            execute_values(
                cursor,
                "INSERT INTO college_docs (filename, chunk_text, embedding) VALUES %s",
                records
            )
            conn.commit()

            elapsed = time.time() - t0
            total_inserted += len(chunks)
            print(f"  -> [SUCCESS] Ingested {len(chunks)} chunks into Neon in {elapsed:.1f}s\n")

        cursor.close()
        conn.close()

        total_time = time.time() - overall_start
        print("=" * 60)
        print(f"All documents successfully indexed! Total chunks: {total_inserted} in {total_time:.1f}s")
        print("=" * 60)
