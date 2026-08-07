import chromadb

class VectorStore:

    def __init__(self, collection_name="renvora_knowledge_v2"):

        self.client = chromadb.PersistentClient(
            path="database/chroma"
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    def add_chunks(self, embedded_chunks):

        if not embedded_chunks:
            return

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for chunk in embedded_chunks:

            ids.append(chunk["chunk_id"])
            documents.append(chunk["text"])
            embeddings.append(chunk["embedding"])

            metadatas.append({
                "pdf_name": chunk["pdf_name"],
                "page": chunk["page"]
            })

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search(self, embedding, top_k=5):

        return self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )

    def delete_by_pdf_name(self, pdf_name):
        try:
            self.collection.delete(
                where={"pdf_name": pdf_name}
            )
        except Exception as e:
            print("Error deleting from ChromaDB:", e)