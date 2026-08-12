"""
services/embeddings.py

Renvora AI Cloud Embedding Engine

Embedding generation is handled by Qdrant Cloud Inference.

The local Render server does NOT load:
    - torch
    - sentence-transformers
    - all-MiniLM-L6-v2

This keeps the backend lightweight enough for Render Free.
"""

import os
from typing import List


class EmbeddingEngine:

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    DIMENSION = 384

    def __init__(self):

        print(
            "[EmbeddingEngine] Initializing Cloud Embedding Engine..."
        )

        self.model_name = os.getenv(
            "QDRANT_EMBEDDING_MODEL",
            self.MODEL_NAME,
        )

        self.dimension = self.DIMENSION

        print(
            "[EmbeddingEngine] Ready. "
            f"provider=Qdrant Cloud Inference, "
            f"model={self.model_name}, "
            f"dimension={self.dimension}"
        )

    # ============================================================
    # SINGLE EMBEDDING
    # ============================================================

    def create_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
    ) -> str:

        if text is None:
            raise ValueError(
                "[EmbeddingEngine] Text cannot be None."
            )

        if not isinstance(text, str):
            text = str(text)

        text = text.strip()

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

        # IMPORTANT:
        # We return the original text.
        #
        # VectorStore sends this text to Qdrant Cloud
        # Inference where the actual embedding is created.
        return text

    # ============================================================
    # QUERY EMBEDDING
    # ============================================================

    def create_query_embedding(
        self,
        text: str,
    ) -> str:

        return self.create_embedding(
            text,
            task_type="retrieval_query",
        )

    # ============================================================
    # INTERNAL DOCUMENT EMBEDDING
    # ============================================================

    def _embed_text(
        self,
        text: str,
    ) -> str:

        return self.create_embedding(
            text,
            task_type="retrieval_document",
        )

    # ============================================================
    # BATCH EMBEDDING
    # ============================================================

    def create_embeddings(
        self,
        chunks: list,
    ) -> list:

        if not chunks:

            print(
                "[EmbeddingEngine] No chunks to embed."
            )

            return []

        embedded_chunks = []

        for index, chunk in enumerate(chunks):

            if not isinstance(chunk, dict):

                print(
                    "[EmbeddingEngine] Skipping invalid chunk "
                    f"{index + 1}/{len(chunks)}."
                )

                continue

            text = str(
                chunk.get("text") or ""
            ).strip()

            if not text:

                print(
                    "[EmbeddingEngine] Skipping empty chunk "
                    f"{index + 1}/{len(chunks)}."
                )

                continue

            # Keep compatibility with existing pipeline.
            #
            # VectorStore will NOT treat this as a real vector.
            # It will send the text to Qdrant Cloud Inference.

            chunk["embedding"] = text

            embedded_chunks.append(chunk)

        print(
            "[EmbeddingEngine] Prepared "
            f"{len(embedded_chunks)}/{len(chunks)} chunks "
            "for Qdrant Cloud Inference."
        )

        return embedded_chunks

    # ============================================================
    # BATCH TEXT HELPER
    # ============================================================

    def create_text_embeddings(
        self,
        texts: List[str],
        batch_size: int = 8,
    ) -> List[str]:

        if not texts:
            return []

        result = []

        for text in texts:

            if text is None:
                continue

            text = str(text).strip()

            if text:
                result.append(text)

        return result

    # ============================================================
    # MODEL INFORMATION
    # ============================================================

    def get_dimension(self) -> int:

        return self.dimension

    def get_model_name(self) -> str:

        return self.model_name