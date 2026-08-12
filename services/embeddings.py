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
    - Batch embedding for document processing

IMPORTANT:
    The SentenceTransformer model is shared between all
    EmbeddingEngine instances inside the same Python process.

    This prevents the same model from being loaded multiple
    times by AIEngine, Retriever, mobile_api, user_pdf, etc.
"""

import os
import threading
from typing import List

from sentence_transformers import SentenceTransformer


class EmbeddingEngine:

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    # ============================================================
    # SHARED MODEL
    # ============================================================

    _shared_models = {}
    _model_lock = threading.Lock()

    # Protect encode operations.
    # This also keeps CPU memory usage more predictable on Render.
    _encode_lock = threading.Lock()

    def __init__(self):

        print(
            "[EmbeddingEngine] Initializing Local Embedding Engine..."
        )

        # --------------------------------------------------------
        # MODEL CONFIGURATION
        # --------------------------------------------------------

        self.model_name = os.getenv(
            "LOCAL_EMBEDDING_MODEL",
            self.MODEL_NAME,
        )

        self.device = os.getenv(
            "EMBEDDING_DEVICE",
            "cpu",
        )

        model_key = (
            self.model_name,
            self.device,
        )

        # --------------------------------------------------------
        # LOAD MODEL ONLY ONCE PER PROCESS
        # --------------------------------------------------------

        if model_key not in EmbeddingEngine._shared_models:

            with EmbeddingEngine._model_lock:

                if model_key not in EmbeddingEngine._shared_models:

                    print(
                        "[EmbeddingEngine] Loading shared "
                        "SentenceTransformer model..."
                    )

                    model = SentenceTransformer(
                        self.model_name,
                        device=self.device,
                    )

                    EmbeddingEngine._shared_models[
                        model_key
                    ] = model

                    print(
                        "[EmbeddingEngine] Shared model loaded."
                    )

        else:

            print(
                "[EmbeddingEngine] Reusing existing "
                "shared model."
            )

        self.model = EmbeddingEngine._shared_models[
            model_key
        ]

        # --------------------------------------------------------
        # DIMENSION
        # --------------------------------------------------------

        self.dimension = (
            self.model.get_sentence_embedding_dimension()
        )

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

        task_type is retained for compatibility with
        the previous Gemini implementation.

        Supported:
            retrieval_document
            retrieval_query
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

            # ----------------------------------------------------
            # One shared encode operation at a time.
            # This is intentionally conservative for Render Free.
            # ----------------------------------------------------

            with EmbeddingEngine._encode_lock:

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
        Create embedding for a user query.

        Retriever already uses this method.
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

        # --------------------------------------------------------
        # VALIDATE CHUNKS
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # BATCH SIZE
        # --------------------------------------------------------
        #
        # Render Free has limited RAM.
        # 8 is safer than the previous default of 32.
        #
        # It can still be overridden:
        #
        # EMBEDDING_BATCH_SIZE=16
        #
        # --------------------------------------------------------

        try:

            batch_size = max(
                1,
                int(
                    os.getenv(
                        "EMBEDDING_BATCH_SIZE",
                        "8",
                    )
                ),
            )

        except (TypeError, ValueError):

            batch_size = 8

        print(
            "[EmbeddingEngine] Starting local batch embedding: "
            f"{len(texts)} chunks."
        )

        print(
            "[EmbeddingEngine] "
            f"batch_size={batch_size}, "
            f"dimension={self.dimension}"
        )

        # --------------------------------------------------------
        # BATCH ENCODE
        # --------------------------------------------------------

        try:

            with EmbeddingEngine._encode_lock:

                embeddings = self.model.encode(
                    texts,
                    batch_size=batch_size,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )

        except Exception as e:

            raise RuntimeError(
                "[EmbeddingEngine] Batch embedding failed: "
                f"{e}"
            ) from e

        # --------------------------------------------------------
        # ATTACH EMBEDDINGS TO CHUNKS
        # --------------------------------------------------------

        embedded_chunks = []

        for chunk, embedding in zip(
            valid_chunks,
            embeddings,
        ):

            chunk["embedding"] = (
                embedding.tolist()
            )

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
        batch_size: int = 8,
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

            with EmbeddingEngine._encode_lock:

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

        return self.dimension

    def get_model_name(self) -> str:

        return self.model_name