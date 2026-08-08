"""
services/retriever.py
─────────────────────
Retrieves relevant chunks from ChromaDB using semantic search.

FIXED: Uses create_query_embedding() (task_type=retrieval_query) for search.
       Previously was using retrieval_document task_type for queries, which
       significantly reduced retrieval accuracy.
"""

import traceback
from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore


class Retriever:

    def __init__(self):
        self.embedding_engine = EmbeddingEngine()

    def search(
        self,
        question: str,
        collection_name: str = "renvora_knowledge_v2",
        top_k: int = 5,
        where: dict = None,
    ) -> dict:
        """
        Search a ChromaDB collection for chunks relevant to the question.

        Args:
            question        : User's question (embedded as retrieval_query).
            collection_name : ChromaDB collection to search.
            top_k           : Number of results to return.
            where           : Optional metadata filter (e.g., {"pdf_name": "report.pdf"}).

        Returns:
            ChromaDB query result dict with keys: ids, documents, distances, metadatas.
            Returns empty result dict on error.
        """
        try:
            # FIXED: Use retrieval_query task_type for search queries
            question_embedding = self.embedding_engine.create_query_embedding(question)

            vector_store = VectorStore(collection_name)
            result = vector_store.search(
                embedding=question_embedding,
                top_k=top_k,
                where=where,
            )
            return result

        except Exception as e:
            traceback.print_exc()
            print(f"[Retriever] ERROR searching '{collection_name}': {e}")
            return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}