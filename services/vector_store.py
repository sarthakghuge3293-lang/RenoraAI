"""
services/vector_store.py

Qdrant Cloud vector storage layer.

Responsibilities:
- Connect to Qdrant Cloud
- Create collections
- Create payload indexes
- Upload document chunks
- Search document chunks
- Delete by doc_id
- Verify document indexing

No source-routing logic lives here.
"""

import os
import uuid
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

load_dotenv(override=True)


class VectorStore:

    MODEL_NAME = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    DIMENSION = 384

    def __init__(
        self,
        collection_name: str,
    ):

        self.collection_name = (
            collection_name
        )

        self.url = os.getenv(
            "QDRANT_URL"
        )

        self.api_key = os.getenv(
            "QDRANT_API_KEY"
        )

        if not self.url:
            raise RuntimeError(
                "[VectorStore] QDRANT_URL is not configured."
            )

        if not self.api_key:
            raise RuntimeError(
                "[VectorStore] QDRANT_API_KEY is not configured."
            )

        try:

            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                cloud_inference=True,
            )

            print(
                "[VectorStore] Connected to Qdrant Cloud."
            )

            self._ensure_collection()

        except Exception as e:

            raise RuntimeError(
                "[VectorStore] Qdrant initialization failed: "
                f"{e}"
            ) from e

    # ============================================================
    # COLLECTION
    # ============================================================

    def _ensure_collection(self):

        try:

            exists = (
                self.client.collection_exists(
                    self.collection_name
                )
            )

            if not exists:

                print(
                    "[VectorStore] Creating collection:",
                    self.collection_name
                )

                self.client.create_collection(

                    collection_name=(
                        self.collection_name
                    ),

                    vectors_config=(
                        models.VectorParams(

                            size=self.DIMENSION,

                            distance=(
                                models.Distance.COSINE
                            )
                        )
                    )
                )

            else:

                print(
                    "[VectorStore] Collection exists:",
                    self.collection_name
                )

            self._ensure_payload_indexes()

        except Exception as e:

            raise RuntimeError(
                "[VectorStore] Collection initialization failed: "
                f"{e}"
            ) from e

    # ============================================================
    # PAYLOAD INDEXES
    # ============================================================

    def _ensure_payload_indexes(self):

        indexes = [
            (
                "doc_id",
                models.PayloadSchemaType.INTEGER,
            ),
            (
                "user_id",
                models.PayloadSchemaType.INTEGER,
            ),
            (
                "pdf_name",
                models.PayloadSchemaType.KEYWORD,
            ),
            (
                "page",
                models.PayloadSchemaType.INTEGER,
            ),
        ]

        for field_name, schema in indexes:

            try:

                self.client.create_payload_index(
                    collection_name=(
                        self.collection_name
                    ),
                    field_name=field_name,
                    field_schema=schema,
                )

            except Exception as e:

                # Index may already exist.
                message = str(e).lower()

                if (
                    "already exists" not in message
                    and "already exist" not in message
                ):
                    print(
                        "[VectorStore] "
                        f"Payload index warning for {field_name}:",
                        e
                    )

    # ============================================================
    # POINT ID
    # ============================================================

    def _point_id(
        self,
        chunk: Dict[str, Any],
    ) -> str:

        raw = (
            f"{self.collection_name}:"
            f"{chunk.get('chunk_id', '')}:"
            f"{chunk.get('doc_id', '')}:"
            f"{chunk.get('page', '')}"
        )

        return str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                raw,
            )
        )

    # ============================================================
    # ADD CHUNKS
    # ============================================================

    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 32,
    ) -> int:

        if not chunks:
            return 0

        points = []

        for chunk in chunks:

            if not isinstance(chunk, dict):
                continue

            text = str(
                chunk.get("text") or ""
            ).strip()

            if not text:
                continue

            doc_id = chunk.get(
                "doc_id",
                0,
            )

            try:
                doc_id = int(doc_id)
            except (
                TypeError,
                ValueError,
            ):
                doc_id = 0

            page = chunk.get(
                "page",
                0,
            )

            try:
                page = int(page)
            except (
                TypeError,
                ValueError,
            ):
                page = 0

            user_id = chunk.get(
                "user_id",
                0,
            )

            try:
                user_id = int(user_id)
            except (
                TypeError,
                ValueError,
            ):
                user_id = 0

            pdf_name = str(
                chunk.get(
                    "pdf_name",
                    "",
                ) or ""
            )

            chunk_id = str(
                chunk.get(
                    "chunk_id",
                    "",
                )
            )

            payload = {

                "text": text,

                "user_id": user_id,

                "doc_id": doc_id,

                "pdf_name": pdf_name,

                "page": page,

                "chunk_id": chunk_id,
            }

            points.append(
                models.PointStruct(

                    id=self._point_id(
                        chunk
                    ),

                    vector=models.Document(
                        text=text,
                        model=self.MODEL_NAME,
                    ),

                    payload=payload,
                )
            )

        if not points:

            return 0

        print(
            "[VectorStore] Uploading "
            f"{len(points)} chunks..."
        )

        try:

            self.client.upload_points(

                collection_name=(
                    self.collection_name
                ),

                points=points,

                batch_size=batch_size,

                wait=True,
            )

            print(
                "[VectorStore] Upload successful:",
                len(points)
            )

            return len(points)

        except Exception as e:

            raise RuntimeError(
                "[VectorStore] Upload failed: "
                f"{e}"
            ) from e

    # ============================================================
    # SEARCH
    # ============================================================

    def search(
        self,
        question: str,
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> Dict[str, Any]:

        if not question or not question.strip():

            return {
                "ids": [[]],
                "documents": [[]],
                "distances": [[]],
                "metadatas": [[]],
            }

        query_filter = (
            self._build_filter(where)
            if where
            else None
        )

        print(
            "[VectorStore] Search:",
            self.collection_name
        )

        print(
            "[VectorStore] Filter:",
            where
        )

        try:

            result = self.client.query_points(

                collection_name=(
                    self.collection_name
                ),

                query=models.Document(
                    text=question.strip(),
                    model=self.MODEL_NAME,
                ),

                limit=int(top_k),

                query_filter=query_filter,

                with_payload=True,
            )

            points = (
                result.points
                if result
                else []
            )

            ids = []
            documents = []
            distances = []
            metadatas = []

            for point in points:

                ids.append(
                    str(point.id)
                )

                payload = (
                    point.payload
                    or {}
                )

                documents.append(
                    str(
                        payload.get(
                            "text",
                            ""
                        )
                    )
                )

                distances.append(
                    float(
                        point.score
                    )
                )

                metadatas.append(
                    payload
                )

            print(
                "[VectorStore] Results:",
                len(points)
            )

            return {

                "ids": [ids],

                "documents": [
                    documents
                ],

                "distances": [
                    distances
                ],

                "metadatas": [
                    metadatas
                ],
            }

        except Exception as e:

            raise RuntimeError(
                "[VectorStore] Search failed: "
                f"{e}"
            ) from e

    # ============================================================
    # FILTER CONVERTER
    # ============================================================

    def _build_filter(
        self,
        where: dict,
    ):

        must = []

        for key, value in where.items():

            if value is None:
                continue

            if key in {
                "doc_id",
                "user_id",
                "page",
            }:

                try:
                    value = int(value)
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

            must.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(
                        value=value
                    ),
                )
            )

        if not must:
            return None

        return models.Filter(
            must=must
        )

    # ============================================================
    # VERIFY DOCUMENT
    # ============================================================

    def count_by_doc_id(
        self,
        doc_id: int,
    ) -> int:

        try:

            result = self.client.count(

                collection_name=(
                    self.collection_name
                ),

                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(
                                value=int(doc_id)
                            ),
                        )
                    ]
                ),

                exact=True,
            )

            return int(
                result.count
            )

        except Exception as e:

            raise RuntimeError(
                "[VectorStore] Document count failed: "
                f"{e}"
            ) from e

    # ============================================================
    # DELETE BY DOC ID
    # ============================================================

    def delete_by_doc_id(
        self,
        doc_id: int,
    ):

        self.client.delete(

            collection_name=(
                self.collection_name
            ),

            points_selector=(
                models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="doc_id",
                                match=models.MatchValue(
                                    value=int(
                                        doc_id
                                    )
                                ),
                            )
                        ]
                    )
                )
            ),

            wait=True,
        )

        print(
            "[VectorStore] Deleted doc_id:",
            doc_id
        )

    # ============================================================
    # DELETE BY PDF NAME
    # ============================================================

    def delete_by_pdf_name(
        self,
        pdf_name: str,
    ):

        if not pdf_name:
            return

        self.client.delete(

            collection_name=(
                self.collection_name
            ),

            points_selector=(
                models.FilterSelector(
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
                )
            ),

            wait=True,
        )