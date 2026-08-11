from services.embeddings import EmbeddingEngine
import chromadb

print("Starting company search test...")

# Local embedding engine
engine = EmbeddingEngine()

# Query embedding
query = "services"
query_embedding = engine.create_query_embedding(query)

print("Query embedding dimension:", len(query_embedding))

# ChromaDB
client = chromadb.PersistentClient(
    path="database/chroma"
)

collection = client.get_collection(
    "renvora_knowledge_local_v1"
)

print("Collection:", collection.name)
print("Documents:", collection.count())

# Search
result = collection.query(
    query_embeddings=[query_embedding],
    n_results=3,
    include=[
        "documents",
        "metadatas",
        "distances",
    ],
)

print("\n========== SEARCH RESULTS ==========\n")

for i, document in enumerate(result["documents"][0]):
    distance = result["distances"][0][i]
    metadata = result["metadatas"][0][i]

    print(f"RESULT {i + 1}")
    print("Distance:", distance)
    print("Metadata:", metadata)
    print("Document:")
    print(document)
    print("\n" + "=" * 60 + "\n")
    from services.retriever import Retriever

print("\n========== RETRIEVER TEST ==========\n")

retriever = Retriever()

results = retriever.search(
    question="services",
    collection_name="renvora_knowledge_local_v1",
    top_k=5,
)

print("RETRIEVER RESULTS:")
print(results)