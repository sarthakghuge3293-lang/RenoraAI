"""
services/embeddings.py

Gemini Embedding Engine.

Embedding rules:

- retrieval_document -> document chunks
- retrieval_query    -> user search/query

IMPORTANT:
Document and query embeddings intentionally use different
Gemini task types for better semantic retrieval accuracy.
"""

import os
import time

import google.generativeai as genai

from config import Config


class EmbeddingEngine:

    def __init__(self):

        print(
            "[EmbeddingEngine] "
            "Initializing Gemini Embedding Engine..."
        )

        api_key = Config.GEMINI_API_KEY

        if not api_key:
            api_key = os.getenv(
                "GEMINI_API_KEY"
            )

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is missing. "
                "Please set it in your environment."
            )

        genai.configure(
            api_key=api_key
        )

        self.model_name = (
            "models/gemini-embedding-001"
        )

        print(
            "[EmbeddingEngine] Ready."
        )

    # ======================================================================
    # SINGLE EMBEDDING
    # ======================================================================

    def create_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
    ) -> list:
        """
        Create one embedding.

        task_type must normally be:

            retrieval_document
                For storing document chunks.

            retrieval_query
                For user/search questions.
        """

        if text is None:
            raise ValueError(
                "[EmbeddingEngine] Text cannot be None."
            )

        if not isinstance(
            text,
            str
        ):
            text = str(text)

        text = text.strip()

        if not text:
            raise ValueError(
                "[EmbeddingEngine] Text cannot be empty."
            )

        valid_task_types = {
            "retrieval_document",
            "retrieval_query",
        }

        if task_type not in valid_task_types:

            raise ValueError(
                "[EmbeddingEngine] Invalid task_type: "
                f"{task_type}. "
                "Expected retrieval_document or "
                "retrieval_query."
            )

        # --------------------------------------------------------------
        # Retry transient API failures.
        # --------------------------------------------------------------

        for attempt in range(3):

            try:

                response = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type=task_type,

                    # Gemini recommends a title for document
                    # embeddings. Query embeddings don't need one.
                    title=(
                        "Renvora Document"
                        if task_type
                        == "retrieval_document"
                        else None
                    ),
                )

                embedding = response.get(
                    "embedding"
                )

                if not embedding:

                    raise RuntimeError(
                        "[EmbeddingEngine] "
                        "Gemini returned an empty embedding."
                    )

                return embedding

            except Exception as e:

                print(
                    "[EmbeddingEngine] "
                    f"Error on attempt "
                    f"{attempt + 1}/3: {e}"
                )

                if attempt < 2:
                    time.sleep(2)

        raise RuntimeError(
            "[EmbeddingEngine] "
            "Failed to create embedding after "
            "3 attempts."
        )

    # ======================================================================
    # QUERY EMBEDDING
    # ======================================================================

    def create_query_embedding(
        self,
        text: str,
    ) -> list:
        """
        Create an embedding for a user's search question.

        IMPORTANT:
        Uses retrieval_query, NOT retrieval_document.
        """

        return self.create_embedding(
            text,
            task_type="retrieval_query",
        )

    # ======================================================================
    # DOCUMENT EMBEDDINGS
    # ======================================================================

    def create_embeddings(
        self,
        chunks: list,
    ) -> list:
        """
        Create embeddings for document chunks.

        Each chunk must normally contain:

            {
                "text": "..."
            }

        The resulting chunk receives:

            {
                "embedding": [...]
            }

        Failed chunks are skipped so that one bad chunk
        doesn't stop the entire document.
        """

        if not chunks:
            print(
                "[EmbeddingEngine] "
                "No chunks to embed."
            )
            return []

        embedded_chunks = []

        total = len(chunks)

        for index, chunk in enumerate(
            chunks
        ):

            try:

                if not isinstance(
                    chunk,
                    dict
                ):
                    print(
                        "[EmbeddingEngine] "
                        f"Skipping invalid chunk "
                        f"{index + 1}/{total}."
                    )
                    continue

                text = chunk.get(
                    "text"
                )

                if not text:
                    print(
                        "[EmbeddingEngine] "
                        f"Skipping empty chunk "
                        f"{index + 1}/{total}."
                    )
                    continue

                print(
                    "[EmbeddingEngine] "
                    f"Embedding chunk "
                    f"{index + 1}/{total}..."
                )

                chunk["embedding"] = (
                    self.create_embedding(
                        text,
                        task_type="retrieval_document",
                    )
                )

                embedded_chunks.append(
                    chunk
                )

            except Exception as e:

                print(
                    "[EmbeddingEngine] "
                    f"Failed to embed chunk "
                    f"{index + 1}/{total}: {e}"
                )

                # Continue processing remaining chunks.

        print(
            "[EmbeddingEngine] "
            f"Embedded "
            f"{len(embedded_chunks)}/{total} "
            f"chunks successfully."
        )

        return embedded_chunks