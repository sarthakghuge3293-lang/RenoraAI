"""
services/vector_store.py

Renvora AI Qdrant Cloud Vector Store.

Qdrant Cloud handles:
- vector storage
- semantic search
- Cloud Inference embeddings
- metadata filtering
"""

import os
import hashlib

from qdrant_client import QdrantClient, models


class VectorStore:

    EMBEDDING_MODEL = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    VECTOR_SIZE = 384

    def __init__(
        self,
        collection_name="renvora_knowledge_local_v1",
    ):

        self.collection_name = collection_name

        self.url = os.getenv("QDRANT_URL")
        self.api_key = os.getenv("QDRANT_API_KEY")

        if not self.url:
            raise RuntimeError(
                "[VectorStore] QDRANT_URL is not configured."
            )

        if not self.api_key:
            raise RuntimeError(
                "[VectorStore] QDRANT_API_KEY is not configured."
            )

        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            cloud_inference=True,
        )

        print(
            "[VectorStore] Connected to Qdrant Cloud."
        )

        self._ensure_collection()

    # ============================================================
    # COLLECTION
    # ============================================================

    def _ensure_collection(self):

        try:

            if not self.client.collection_exists(
                self.collection_name
            ):

                print(
                    "[VectorStore] Creating collection:",
                    self.collection_name,
                )

                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=models.Distance.COSINE,
                    ),
                )

            else:

                print(
                    "[VectorStore] Collection exists:",
                    self.collection_name,
                )

        except Exception as e:

            raise RuntimeError(
                "[VectorStore] Collection initialization failed: "
                f"{e}"
            ) from e

    # ============================================================
    # POINT ID
    # ============================================================

    def _make_point_id(self, chunk_id):

        return hashlib.md5(
            str(chunk_id).encode("utf-8")
        ).hexdigest()

    # ============================================================
    # ADD CHUNKS
    # ============================================================

    def add_chunks(self, embedded_chunks):

        if not embedded_chunks:
            return

        points = []

        for chunk in embedded_chunks:

            chunk_id = chunk.get("chunk_id")

            text = str(
                chunk.get("text") or ""
            ).strip()

            if not chunk_id or not text:
                continue

            try:

                doc_id = int(
                    chunk.get("doc_id", 0)
                )

            except (
                TypeError,
                ValueError,
            ):

                doc_id = 0

            try:

                page = int(
                    chunk.get("page", 0)
                )

            except (
                TypeError,
                ValueError,
            ):

                page = 0

            pdf_name = str(
                chunk.get(
                    "pdf_name",
                    "",
                )
                or ""
            )

            payload = {
                "text": text,
                "pdf_name": pdf_name,
                "doc_id": doc_id,
                "page": page,
            }

            point = models.PointStruct(

                id=self._make_point_id(
                    chunk_id
                ),

                vector=models.Document(
                    text=text,
                    model=self.EMBEDDING_MODEL,
                ),

                payload=payload,
            )

            points.append(point)

        if not points:
            print(
                "[VectorStore] No valid chunks."
            )
            return

        print(
            "[VectorStore] Uploading",
            len(points),
            "chunks..."
        )

        try:

            self.client.upload_points(
                collection_name=self.collection_name,
                points=points,
            )

            print(
                "[VectorStore] Upload successful:",
                len(points),
            )

        except Exception as e:

            print(
                "[VectorStore] Upload failed:",
                e,
            )

            raise

    # ============================================================
    # FILTER
    # ============================================================

    def _build_filter(self, where=None):

        if not where:
            return None

        conditions = []

        for key, value in where.items():

            if value is None:
                continue

            if key == "doc_id":

                try:
                    value = int(value)

                except (
                    TypeError,
                    ValueError,
                ):

                    continue

            conditions.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(
                        value=value
                    ),
                )
            )

        if not conditions:
            return None

        return models.Filter(
            must=conditions
        )

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        embedding,
        top_k=5,
        where=None,
    ):

        if not embedding:
            return self._empty_result()

        query_text = str(
            embedding
        ).strip()

        if not query_text:
            return self._empty_result()

        query_filter = (
            self._build_filter(where)
        )

        try:

            response = self.client.query_points(

                collection_name=self.collection_name,

                query=models.Document(
                    text=query_text,
                    model=self.EMBEDDING_MODEL,
                ),

                query_filter=query_filter,

                limit=max(
                    1,
                    min(
                        int(top_k),
                        20,
                    ),
                ),

                with_payload=True,
            )

            return self._normalize_results(
                response
            )

        except Exception as e:

            print(
                "[VectorStore] Search error:",
                e,
            )

            return self._empty_result()

    # ============================================================
    # SEARCH BY DOCUMENT ID
    # ============================================================

    def search_by_doc_id(
        self,
        embedding,
        doc_id,
        top_k=5,
    ):

        if doc_id is None:
            return self._empty_result()

        try:

            doc_id = int(doc_id)

        except (
            TypeError,
            ValueError,
        ):

            return self._empty_result()

        return self.search(
            embedding=embedding,
            top_k=top_k,
            where={
                "doc_id": doc_id
            },
        )

    # ============================================================
    # DELETE BY DOCUMENT ID
    # ============================================================

    def delete_by_doc_id(self, doc_id):

        if doc_id is None:
            return

        try:

            doc_id = int(doc_id)

            self.client.delete(

                collection_name=self.collection_name,

                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="doc_id",
                                match=models.MatchValue(
                                    value=doc_id
                                ),
                            )
                        ]
                    )
                ),
            )

            print(
                "[VectorStore] Deleted doc_id:",
                doc_id,
            )

        except Exception as e:

            print(
                "[VectorStore] Delete error:",
                e,
            )

    # ============================================================
    # DELETE BY PDF NAME
    # ============================================================

    def delete_by_pdf_name(self, pdf_name):

        if not pdf_name:
            return

        try:

            self.client.delete(

                collection_name=self.collection_name,

                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="pdf_name",
                                match=models.MatchValue(
                                    value=pdf_name
                                ),
                            )
                        ]
                    )
                ),
            )

            print(
                "[VectorStore] Deleted PDF:",
                pdf_name,
            )

        except Exception as e:

            print(
                "[VectorStore] PDF delete error:",
                e,
            )

    # ============================================================
    # NORMALIZE RESULTS
    # ============================================================

    def _normalize_results(self, response):

        documents = []
        distances = []
        ids = []
        metadatas = []

        points = getattr(
            response,
            "points",
            [],
        )

        for point in points:

            payload = (
                getattr(
                    point,
                    "payload",
                    None,
                )
                or {}
            )

            text = str(
                payload.get(
                    "text",
                    "",
                )
                or ""
            )

            if not text:
                continue

            point_id = getattr(
                point,
                "id",
                "",
            )

            score = getattr(
                point,
                "score",
                0.0,
            )

            try:

                distance = 1.0 - float(score)

            except Exception:

                distance = 999.0

            documents.append(text)
            distances.append(distance)
            ids.append(str(point_id))

            metadatas.append({
                "pdf_name": payload.get(
                    "pdf_name",
                    "",
                ),
                "doc_id": payload.get(
                    "doc_id",
                    0,
                ),
                "page": payload.get(
                    "page",
                    0,
                ),
            })

        return {
            "ids": [ids],
            "documents": [documents],
            "distances": [distances],
            "metadatas": [metadatas],
        }

    # ============================================================
    # EMPTY RESULT
    # ============================================================

    @staticmethod
    def _empty_result():

        return {
            "ids": [[]],
            "documents": [[]],
            "distances": [[]],
            "metadatas": [[]],
        }