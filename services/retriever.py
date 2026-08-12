"""
services/retriever.py

Renvora AI semantic retrieval layer.

Uses Qdrant Cloud for:
    - embedding inference
    - vector search
    - metadata filtering
"""

from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore


class Retriever:

    def __init__(self):

        self.embedding_engine = (
            EmbeddingEngine()
        )

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        question: str,
        collection_name: str = (
            "renvora_knowledge_local_v1"
        ),
        top_k: int = 5,
        where: dict = None,
    ) -> dict:

        empty_result = {
            "ids": [[]],
            "documents": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }

        try:

            # ----------------------------------------------------
            # Validate question
            # ----------------------------------------------------

            if not question or not question.strip():

                print(
                    "[Retriever] Empty question."
                )

                return empty_result

            question = question.strip()

            # ----------------------------------------------------
            # Validate collection
            # ----------------------------------------------------

            if not collection_name:

                print(
                    "[Retriever] Collection name is empty."
                )

                return empty_result

            # ----------------------------------------------------
            # Validate top_k
            # ----------------------------------------------------

            try:

                top_k = int(top_k)

            except (
                TypeError,
                ValueError,
            ):

                top_k = 5

            top_k = max(
                1,
                min(
                    top_k,
                    20,
                ),
            )

            print(
                "[Retriever] Searching:"
                f" collection={collection_name}"
                f" top_k={top_k}"
                f" where={where}"
            )

            # ----------------------------------------------------
            # IMPORTANT
            #
            # No local embedding is generated.
            #
            # Qdrant Cloud will create the query embedding.
            # ----------------------------------------------------

            query_text = (
                self.embedding_engine
                .create_query_embedding(
                    question
                )
            )

            if not query_text:

                print(
                    "[Retriever] Query text is empty."
                )

                return empty_result

            # ----------------------------------------------------
            # QDRANT
            # ----------------------------------------------------

            vector_store = VectorStore(
                collection_name
            )

            result = vector_store.search(
                embedding=query_text,
                top_k=top_k,
                where=where,
            )

            if not result:

                return empty_result

            return result

        except Exception as e:

            print(
                "[Retriever] Search error:",
                e,
            )

            return empty_result