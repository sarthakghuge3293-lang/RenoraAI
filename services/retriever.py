"""
services/retriever.py

Renvora AI semantic retrieval layer.

Responsibilities:
- Convert the user's question into a retrieval-query embedding.
- Search the requested ChromaDB collection.
- Support metadata filtering for specific uploaded documents.
- Preserve document metadata for source identification.
- Return safe empty results on retrieval errors.
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
        Search a ChromaDB collection using semantic retrieval.

        Args:
            question:
                Current user question.

            collection_name:
                ChromaDB collection to search.

            top_k:
                Maximum number of chunks to retrieve.

            where:
                Optional ChromaDB metadata filter.

                Example:
                    {"pdf_name": "XYZ_Company.pdf"}

        Returns:
            {
                "ids": [...],
                "documents": [...],
                "distances": [...],
                "metadatas": [...]
            }
        """

        empty_result = {
            "ids": [[]],
            "documents": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }

        try:
            # --------------------------------------------------------------
            # Validate question
            # --------------------------------------------------------------

            if not question or not question.strip():
                print("[Retriever] Empty question.")
                return empty_result

            question = question.strip()

            # --------------------------------------------------------------
            # Validate collection
            # --------------------------------------------------------------

            if not collection_name:
                print("[Retriever] Collection name is empty.")
                return empty_result

            # --------------------------------------------------------------
            # Validate top_k
            # --------------------------------------------------------------

            try:
                top_k = int(top_k)
            except (TypeError, ValueError):
                top_k = 5

            top_k = max(1, min(top_k, 20))

            # --------------------------------------------------------------
            # Create query embedding
            #
            # IMPORTANT:
            # User questions MUST use retrieval_query.
            # --------------------------------------------------------------

            question_embedding = (
                self.embedding_engine.create_query_embedding(
                    question
                )
            )

            if not question_embedding:
                print(
                    "[Retriever] Query embedding is empty."
                )
                return empty_result

            # --------------------------------------------------------------
            # Search ChromaDB
            # --------------------------------------------------------------

            vector_store = VectorStore(
                collection_name
            )

            result = vector_store.search(
                embedding=question_embedding,
                top_k=top_k,
                where=where,
            )

            if not result:
                return empty_result

            # --------------------------------------------------------------
            # Normalize result structure
            # --------------------------------------------------------------

            ids = result.get(
                "ids",
                [[]]
            )

            documents = result.get(
                "documents",
                [[]]
            )

            distances = result.get(
                "distances",
                [[]]
            )

            metadatas = result.get(
                "metadatas",
                [[]]
            )

            # Chroma normally returns nested lists.
            if ids is None:
                ids = [[]]

            if documents is None:
                documents = [[]]

            if distances is None:
                distances = [[]]

            if metadatas is None:
                metadatas = [[]]

            # --------------------------------------------------------------
            # Return normalized result
            # --------------------------------------------------------------

            return {
                "ids": ids,
                "documents": documents,
                "distances": distances,
                "metadatas": metadatas,
            }

        except Exception as e:

            print(
                f"[Retriever] ERROR searching "
                f"'{collection_name}': {e}"
            )

            traceback.print_exc()

            return empty_result

    # ======================================================================
    # DOCUMENT-SPECIFIC SEARCH
    # ======================================================================

    def search_document(
        self,
        question: str,
        collection_name: str,
        document_name: str,
        top_k: int = 5,
    ) -> dict:
        """
        Search only inside one uploaded document.

        This is useful when the user explicitly refers to:

            "XYZ company PDF"
            "my joining letter"
            "that document"

        and we already know the document name.
        """

        if not document_name:
            return self.search(
                question=question,
                collection_name=collection_name,
                top_k=top_k,
            )

        return self.search(
            question=question,
            collection_name=collection_name,
            top_k=top_k,
            where={
                "pdf_name": document_name
            },
        )

    # ======================================================================
    # SEARCH RESULT HELPER
    # ======================================================================

    @staticmethod
    def get_best_distance(
        result: dict
    ) -> float:
        """
        Return the best semantic distance from a search result.

        Lower distance generally means a stronger semantic match.

        Returns:
            float
            999.0 when no valid result exists.
        """

        try:

            distances = result.get(
                "distances",
                []
            )

            if not distances:
                return 999.0

            if not distances[0]:
                return 999.0

            valid_distances = [
                float(distance)
                for distance in distances[0]
                if distance is not None
            ]

            if not valid_distances:
                return 999.0

            return min(valid_distances)

        except Exception:
            return 999.0

    # ======================================================================
    # FILTER RELEVANT RESULTS
    # ======================================================================

    @staticmethod
    def filter_relevant(
        result: dict,
        max_distance: float = 1.20,
    ) -> dict:
        """
        Filter out weak semantic matches.

        This keeps:
            IDs
            documents
            distances
            metadata

        aligned with each other.
        """

        try:

            documents = result.get(
                "documents",
                [[]]
            )

            distances = result.get(
                "distances",
                [[]]
            )

            ids = result.get(
                "ids",
                [[]]
            )

            metadatas = result.get(
                "metadatas",
                [[]]
            )

            if not documents or not documents[0]:
                return {
                    "ids": [[]],
                    "documents": [[]],
                    "distances": [[]],
                    "metadatas": [[]],
                }

            docs = documents[0]
            dists = (
                distances[0]
                if distances and distances[0]
                else []
            )

            result_ids = (
                ids[0]
                if ids and ids[0]
                else []
            )

            result_metadata = (
                metadatas[0]
                if metadatas and metadatas[0]
                else []
            )

            filtered_ids = []
            filtered_docs = []
            filtered_distances = []
            filtered_metadata = []

            for index, doc in enumerate(docs):

                if index >= len(dists):
                    continue

                distance = dists[index]

                if distance is None:
                    continue

                try:
                    distance = float(distance)
                except (TypeError, ValueError):
                    continue

                if distance > max_distance:
                    continue

                filtered_docs.append(doc)
                filtered_distances.append(distance)

                if index < len(result_ids):
                    filtered_ids.append(
                        result_ids[index]
                    )

                if index < len(result_metadata):
                    filtered_metadata.append(
                        result_metadata[index]
                    )

            return {
                "ids": [filtered_ids],
                "documents": [filtered_docs],
                "distances": [filtered_distances],
                "metadatas": [filtered_metadata],
            }

        except Exception as e:

            print(
                f"[Retriever] Filtering error: {e}"
            )

            return {
                "ids": [[]],
                "documents": [[]],
                "distances": [[]],
                "metadatas": [[]],
            }