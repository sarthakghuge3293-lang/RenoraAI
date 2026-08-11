"""
services/embeddings.py

Renvora AI Local Embedding Engine

Uses:
    sentence-transformers/all-MiniLM-L6-v2

Purpose:
- Company Knowledge query embeddings
- Company Knowledge document embeddings
- User PDF embeddings
- No Gemini Embedding API
- No Gemini embedding quota / 429 dependency
- Batch embedding for faster document processing

The public interface is intentionally kept compatible with
the existing Retriever:
    create_embedding()
    create_query_embedding()
    create_embeddings()
"""

import os
from typing import List, Dict, Any

from sentence_transformers import SentenceTransformer


class EmbeddingEngine:
    """
    Local embedding engine.

    The model is loaded only once when the application starts.
    """

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self):
        print("[EmbeddingEngine] Initializing Local Embedding Engine...")

        # Optional environment override.
        model_name = os.getenv(
            "LOCAL_EMBEDDING_MODEL",
            self.MODEL_NAME,
        )

        self.model_name = model_name

        # CPU is safest for the current setup.
        # If a GPU is available later, this can be changed to "cuda".
        self.device = os.getenv(
            "EMBEDDING_DEVICE",
            "cpu",
        )

        # Load model exactly once.
        self.model = SentenceTransformer(
            self.model_name,
            device=self.device,
        )

        # all-MiniLM-L6-v2 produces 384-dimensional vectors.
        self.dimension = self.model.get_sentence_embedding_dimension()

        print(
            "[EmbeddingEngine] Ready. "
            f"model={self.model_name}, "
            f"device={self.device}, "
            f"dimension={self.dimension}"
        )

    # ============================================================
    # SINGLE TEXT EMBEDDING
    # ============================================================

    def create_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
    ) -> List[float]:
        """
        Create one local embedding.

        task_type is kept for compatibility with the old Gemini
        implementation.

        Supported values:
            retrieval_document
            retrieval_query

        Both use the same local embedding model because the
        sentence-transformer model does not require Gemini's
        task_type parameter.
        """

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
                f"{task_type}. Expected "
                "retrieval_document or retrieval_query."
            )

        try:
            embedding = self.model.encode(
                text,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            return embedding.tolist()

        except Exception as e:
            raise RuntimeError(
                "[EmbeddingEngine] Local embedding failed: "
                f"{e}"
            ) from e

    # ============================================================
    # QUERY EMBEDDING
    # ============================================================

    def create_query_embedding(
        self,
        text: str,
    ) -> List[float]:
        """
        Create an embedding for a user query.

        Retriever already calls this method, so keeping the same
        method name means retriever.py does not need to change.
        """

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
    ) -> List[float]:
        """
        Internal helper used for document chunks.
        """

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
        """
        Create embeddings for document chunks.

        Uses batch encoding instead of making one Gemini API call
        per chunk.

        Existing chunk dictionaries are preserved and receive:

            chunk["embedding"] = [...]

        Returns:
            List of successfully embedded chunks.
        """

        if not chunks:
            print(
                "[EmbeddingEngine] No chunks to embed."
            )
            return []

        total = len(chunks)

        valid_chunks = []
        texts = []

        for index, chunk in enumerate(chunks):

            if not isinstance(chunk, dict):
                print(
                    "[EmbeddingEngine] Skipping invalid chunk "
                    f"{index + 1}/{total}."
                )
                continue

            text = str(
                chunk.get("text") or ""
            ).strip()

            if not text:
                print(
                    "[EmbeddingEngine] Skipping empty chunk "
                    f"{index + 1}/{total}."
                )
                continue

            valid_chunks.append(chunk)
            texts.append(text)

        if not valid_chunks:
            print(
                "[EmbeddingEngine] No valid chunks found."
            )
            return []

        print(
            "[EmbeddingEngine] Starting local batch embedding: "
            f"{len(texts)} chunks."
        )

        # Configurable batch size.
        try:
            batch_size = max(
                1,
                int(
                    os.getenv(
                        "EMBEDDING_BATCH_SIZE",
                        "32",
                    )
                ),
            )
        except ValueError:
            batch_size = 32

        print(
            "[EmbeddingEngine] "
            f"batch_size={batch_size}, "
            f"dimension={self.dimension}"
        )

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=True,
            )

        except Exception as e:
            raise RuntimeError(
                "[EmbeddingEngine] Batch embedding failed: "
                f"{e}"
            ) from e

        embedded_chunks = []

        for chunk, embedding in zip(
            valid_chunks,
            embeddings,
        ):
            chunk["embedding"] = embedding.tolist()
            embedded_chunks.append(chunk)

        print(
            "[EmbeddingEngine] Successfully embedded "
            f"{len(embedded_chunks)}/{len(valid_chunks)} chunks."
        )

        return embedded_chunks

    # ============================================================
    # BATCH TEXT EMBEDDING HELPER
    # ============================================================

    def create_text_embeddings(
        self,
        texts: List[str],
        batch_size: int = 32,
    ) -> List[List[float]]:
        """
        Direct batch embedding helper.

        Useful for migration/re-indexing scripts.
        """

        if not texts:
            return []

        cleaned_texts = []

        for text in texts:
            if text is None:
                continue

            text = str(text).strip()

            if text:
                cleaned_texts.append(text)

        if not cleaned_texts:
            return []

        try:
            embeddings = self.model.encode(
                cleaned_texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

        except Exception as e:
            raise RuntimeError(
                "[EmbeddingEngine] Batch text embedding failed: "
                f"{e}"
            ) from e

        return [
            embedding.tolist()
            for embedding in embeddings
        ]

    # ============================================================
    # MODEL INFORMATION
    # ============================================================

    def get_dimension(self) -> int:
        """
        Return embedding vector dimension.
        """

        return int(self.dimension)

    def get_model_name(self) -> str:
        """
        Return current local embedding model name.
        """

        return self.model_name