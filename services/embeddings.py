"""
services/embeddings.py

Qdrant Cloud Inference embedding adapter.

IMPORTANT:
- No local SentenceTransformer.
- No Gemini embedding API.
- No local embedding model in Render.
- Qdrant Cloud creates embeddings using:
    sentence-transformers/all-MiniLM-L6-v2

The class keeps the old public method names so existing upload
code remains compatible.
"""

from typing import List, Dict, Any

from qdrant_client import models


class EmbeddingEngine:

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSION = 384

    def __init__(self):
        print(
            "[EmbeddingEngine] Ready. "
            "provider=Qdrant Cloud Inference, "
            f"model={self.MODEL_NAME}, "
            f"dimension={self.DIMENSION}"
        )

    # ============================================================
    # SINGLE EMBEDDING
    # ============================================================

    def create_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
    ):
        """
        Return a Qdrant Cloud Inference Document.

        The actual numeric vector is generated inside Qdrant Cloud.
        """

        if text is None:
            raise ValueError(
                "[EmbeddingEngine] Text cannot be None."
            )

        text = str(text).strip()

        if not text:
            raise ValueError(
                "[EmbeddingEngine] Text cannot be empty."
            )

        if task_type not in {
            "retrieval_document",
            "retrieval_query",
        }:
            raise ValueError(
                "[EmbeddingEngine] Invalid task_type: "
                f"{task_type}"
            )

        return models.Document(
            text=text,
            model=self.MODEL_NAME,
        )

    # ============================================================
    # QUERY EMBEDDING
    # ============================================================

    def create_query_embedding(
        self,
        text: str,
    ):
        return self.create_embedding(
            text,
            task_type="retrieval_query",
        )

    # ============================================================
    # DOCUMENT EMBEDDINGS
    # ============================================================

    def create_embeddings(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Validate chunks.

        Qdrant Cloud performs the real embedding when the chunks
        are uploaded.

        This preserves compatibility with existing upload code.
        """

        if not chunks:
            return []

        valid_chunks = []

        for index, chunk in enumerate(chunks):

            if not isinstance(chunk, dict):
                print(
                    "[EmbeddingEngine] "
                    f"Skipping invalid chunk {index + 1}."
                )
                continue

            text = str(
                chunk.get("text") or ""
            ).strip()

            if not text:
                print(
                    "[EmbeddingEngine] "
                    f"Skipping empty chunk {index + 1}."
                )
                continue

            clean_chunk = dict(chunk)

            clean_chunk["text"] = text

            # Compatibility marker.
            clean_chunk["embedding_provider"] = (
                "qdrant_cloud_inference"
            )

            clean_chunk["embedding_model"] = (
                self.MODEL_NAME
            )

            valid_chunks.append(
                clean_chunk
            )

        print(
            "[EmbeddingEngine] Prepared "
            f"{len(valid_chunks)}/{len(chunks)} chunks "
            "for Qdrant Cloud Inference."
        )

        return valid_chunks

    # ============================================================
    # TEXT BATCH HELPER
    # ============================================================

    def create_text_embeddings(
        self,
        texts: List[str],
        batch_size: int = 32,
    ):
        """
        Compatibility helper.

        Returns Qdrant Document objects instead of local vectors.
        """

        if not texts:
            return []

        results = []

        for text in texts:

            if text is None:
                continue

            text = str(text).strip()

            if not text:
                continue

            results.append(
                self.create_embedding(
                    text,
                    task_type="retrieval_document",
                )
            )

        return results

    # ============================================================
    # MODEL INFO
    # ============================================================

    def get_model_name(self) -> str:
        return self.MODEL_NAME

    def get_dimension(self) -> int:
        return self.DIMENSION

    @property
    def dimension(self) -> int:
        return self.DIMENSION