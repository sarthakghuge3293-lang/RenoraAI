"""
services/embeddings.py
──────────────────────
Gemini Embedding Engine.

FIXED: task_type differentiation:
  - 'retrieval_document' for storing document chunks
  - 'retrieval_query'    for search queries
Using the wrong task_type for queries reduces retrieval accuracy significantly.
"""

import os
import time
import google.generativeai as genai
from config import Config


class EmbeddingEngine:

    def __init__(self):
        print("[EmbeddingEngine] Initializing Gemini Embedding Engine...")

        api_key = Config.GEMINI_API_KEY
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing. Please set it in your .env file.")

        genai.configure(api_key=api_key)
        self.model_name = "models/gemini-embedding-001"
        print("[EmbeddingEngine] Ready.")

    def create_embedding(self, text: str, task_type: str = "retrieval_document") -> list:
        """
        Create a single embedding.

        Args:
            text      : Text to embed.
            task_type : 'retrieval_document' (for storage) or
                        'retrieval_query' (for search queries).
                        Using the correct task_type significantly improves retrieval accuracy.
        """
        if not isinstance(text, str):
            text = str(text)

        # Retry up to 3 times on transient API errors
        for attempt in range(3):
            try:
                response = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type=task_type,
                    title="Renvora Document" if task_type == "retrieval_document" else None,
                )
                return response['embedding']
            except Exception as e:
                print(f"[EmbeddingEngine] Error on attempt {attempt + 1}: {e}")
                if attempt < 2:
                    time.sleep(2)
        raise RuntimeError("[EmbeddingEngine] Failed to create embedding after 3 attempts.")

    def create_query_embedding(self, text: str) -> list:
        """Convenience method — uses retrieval_query task_type for search."""
        return self.create_embedding(text, task_type="retrieval_query")

    def create_embeddings(self, chunks: list) -> list:
        """Embed a list of document chunks (task_type=retrieval_document)."""
        embedded_chunks = []
        total = len(chunks)

        for index, chunk in enumerate(chunks):
            try:
                print(f"[EmbeddingEngine] Embedding chunk {index + 1}/{total}...")
                chunk["embedding"] = self.create_embedding(
                    chunk["text"], task_type="retrieval_document"
                )
                embedded_chunks.append(chunk)
            except Exception as e:
                print(f"[EmbeddingEngine] Failed to embed chunk {index + 1}: {e}")
                # Skip the failed chunk but continue processing others

        print(f"[EmbeddingEngine] Embedded {len(embedded_chunks)}/{total} chunks successfully.")
        return embedded_chunks