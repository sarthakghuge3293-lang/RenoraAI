import chromadb


class VectorStore:

    def __init__(self, collection_name="renvora_knowledge_local_v1"):

        self.client = chromadb.PersistentClient(
            path="database/chroma"
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    # ============================================================
    # ADD CHUNKS
    # ============================================================

    def add_chunks(self, embedded_chunks):

        if not embedded_chunks:
            return

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for chunk in embedded_chunks:

            chunk_id = chunk.get("chunk_id")
            text = chunk.get("text")
            embedding = chunk.get("embedding")

            if not chunk_id or not text or embedding is None:
                continue

            ids.append(chunk_id)
            documents.append(text)
            embeddings.append(embedding)

            metadatas.append({
                "pdf_name": chunk.get("pdf_name", ""),
                "doc_id": int(chunk.get("doc_id", 0)),
                "page": int(chunk.get("page", 0)),
            })

        if not ids:
            return

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        embedding,
        top_k=5,
        where=None,
    ):

        kwargs = {
            "query_embeddings": [embedding],
            "n_results": top_k,
        }

        if where:
            kwargs["where"] = where

        return self.collection.query(**kwargs)

    # ============================================================
    # SEARCH BY EXACT DOCUMENT ID
    # ============================================================

    def search_by_doc_id(
        self,
        embedding,
        doc_id,
        top_k=5,
    ):
        """
        Search ONLY inside one exact uploaded document.

        This prevents:
            PDF A -> PDF B leakage
            same filename collisions
            other user's document leakage
        """

        if doc_id is None:
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }

        try:
            doc_id = int(doc_id)
        except (TypeError, ValueError):
            return {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            }

        return self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={
                "doc_id": doc_id
            },
        )

    # ============================================================
    # DELETE BY EXACT DOCUMENT ID
    # ============================================================

    def delete_by_doc_id(self, doc_id):

        if doc_id is None:
            return

        try:
            doc_id = int(doc_id)

            self.collection.delete(
                where={
                    "doc_id": doc_id
                }
            )

            print(
                f"[VectorStore] Deleted vectors for doc_id={doc_id}"
            )

        except Exception as e:

            print(
                f"[VectorStore] Error deleting doc_id={doc_id}:",
                e,
            )

    # ============================================================
    # OLD DELETE METHOD
    # ============================================================

    def delete_by_pdf_name(self, pdf_name):

        """
        Kept for backward compatibility.

        New code should use delete_by_doc_id().
        """

        if not pdf_name:
            return

        try:

            self.collection.delete(
                where={
                    "pdf_name": pdf_name
                }
            )

        except Exception as e:

            print(
                "Error deleting from ChromaDB:",
                e,
            )