import os
import sys
import sqlite3

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import chromadb
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "renvora.db")
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "chroma")

def migrate_collection(client, engine, old_name, new_name, filter_where=None, inject_doc_id=None):
    try:
        old_collection = client.get_collection(old_name)
    except Exception as e:
        print(f"  [!] Old collection '{old_name}' not found: {e}")
        return False

    try:
        if filter_where:
            data = old_collection.get(where=filter_where)
        else:
            data = old_collection.get()
    except Exception as e:
        print(f"  [!] Error reading from '{old_name}': {e}")
        return False

    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])

    if not ids:
        print(f"  [=] No documents found in '{old_name}' to migrate.")
        return True

    print(f"  [*] Found {len(ids)} chunks to migrate. Generating local embeddings...")

    chunks = []
    for i in range(len(ids)):
        meta = metadatas[i] or {}
        chunk = {
            "chunk_id": ids[i],
            "text": documents[i],
            "pdf_name": meta.get("pdf_name", "unknown"),
            "page": meta.get("page", 1),
            "doc_id": inject_doc_id if inject_doc_id is not None else meta.get("doc_id", 0)
        }
        chunks.append(chunk)

    # Generate new embeddings in batches
    embedded_chunks = engine.create_embeddings(chunks)

    if embedded_chunks:
        print(f"  [*] Saving {len(embedded_chunks)} chunks to '{new_name}'...")
        vstore = VectorStore(collection_name=new_name)
        vstore.add_chunks(embedded_chunks)
        print("  [+] Migration for this collection successful.")
        return True
    else:
        print("  [!] Failed to generate embeddings.")
        return False


def run_migration():
    print("=" * 60)
    print("Renvora AI - Local Embeddings Migration")
    print("=" * 60)

    print("[1] Initializing Local Embedding Engine...")
    engine = EmbeddingEngine()

    print(f"\n[2] Connecting to ChromaDB at {CHROMA_PATH}...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    print("\n[3] Migrating Company Knowledge...")
    old_company = "renvora_knowledge_v2"
    new_company = "renvora_knowledge_local_v1"
    migrate_collection(client, engine, old_company, new_company, inject_doc_id=0)

    print("\n[4] Migrating User Documents...")
    if not os.path.exists(DB_PATH):
        print(f"  [!] SQLite database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user_documents")
    documents = cursor.fetchall()

    for doc in documents:
        doc_id = doc["id"]
        user_id = doc["user_id"]
        file_name = doc["file_name"]
        old_collection = doc["collection_name"]
        
        print(f"\n  -> Processing Document ID: {doc_id} | Name: {file_name}")

        if old_collection.endswith("_local_v1"):
            print(f"  [=] Document already migrated to {old_collection}. Skipping.")
            continue

        new_collection = f"user_{user_id}_local_v1"
        print(f"  [*] Migrating chunks for {file_name} from {old_collection} to {new_collection}...")

        # Filter by pdf_name to only grab chunks for this specific document
        success = migrate_collection(
            client=client, 
            engine=engine, 
            old_name=old_collection, 
            new_name=new_collection,
            filter_where={"pdf_name": file_name},
            inject_doc_id=doc_id
        )

        if success:
            print(f"  [+] Updating database for document {doc_id}...")
            cursor.execute(
                "UPDATE user_documents SET collection_name = ? WHERE id = ?",
                (new_collection, doc_id)
            )
            conn.commit()

    conn.close()
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
