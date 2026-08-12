"""
services/retriever.py

Thin retrieval layer.

Retriever does not decide the source.
It only searches the collection it is given.
"""

from services.vector_store import VectorStore


class Retriever:

    def search(
        self,
        question: str,
        collection_name: str,
        top_k: int = 5,
        where: dict = None,
    ) -> dict:

        if not question or not question.strip():
            return {
                "ids": [[]],
                "documents": [[]],
                "distances": [[]],
                "metadatas": [[]],
            }

        if not collection_name:
            raise ValueError(
                "[Retriever] collection_name is required."
            )

        top_k = max(
            1,
            min(
                int(top_k),
                20,
            ),
        )

        print(
            "[Retriever] Searching:",
            f"collection={collection_name}",
            f"top_k={top_k}",
            f"where={where}",
        )

        store = VectorStore(
            collection_name
        )

        result = store.search(
            question=question,
            top_k=top_k,
            where=where,
        )

        documents = (
            result.get(
                "documents",
                [[]]
            )
            or [[]]
        )

        distances = (
            result.get(
                "distances",
                [[]]
            )
            or [[]]
        )

        first_documents = (
            documents[0]
            if documents
            else []
        )

        first_distances = (
            distances[0]
            if distances
            else []
        )

        print(
            "[Retriever] Results:",
            len(first_documents)
        )

        if first_distances:

            print(
                "[Retriever] Best score:",
                first_distances[0]
            )

        return result