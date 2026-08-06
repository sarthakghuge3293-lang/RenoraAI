import importlib


class EmbeddingEngine:

    def __init__(self):

        try:
            sentence_transformers = importlib.import_module("sentence_transformers")
        except ImportError:
            raise ImportError(
                "The 'sentence-transformers' package is required. Install it with 'pip install sentence-transformers'."
            )

        print("Loading Embedding Model...")

        self.model = sentence_transformers.SentenceTransformer(
            "BAAI/bge-small-en-v1.5"
        )

        print("Embedding Model Ready")

    def create_embedding(self, text):

        embedding = self.model.encode(
            text,
            normalize_embeddings=True
        )

        return embedding.tolist()

    def create_embeddings(self, chunks):

        embedded_chunks = []

        total = len(chunks)

        for index, chunk in enumerate(chunks):

            print(f"Embedding {index + 1}/{total}")

            chunk["embedding"] = self.create_embedding(
                chunk["text"]
            )

            embedded_chunks.append(chunk)

        return embedded_chunks