from services.embeddings import EmbeddingEngine
from services.vector_store import VectorStore


class Retriever:

    def __init__(self):

        self.embedding_engine = EmbeddingEngine()

    def search(
            self,
            question,
            collection_name="renvora_knowledge_v2",
            top_k=5,
            where=None
    ):

        question_embedding = self.embedding_engine.create_embedding(
            question
        )

        vector_store = VectorStore(collection_name)

        result = vector_store.search(
            embedding=question_embedding,
            top_k=top_k,
            where=where
        )

        return result