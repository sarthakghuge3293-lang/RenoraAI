from google import genai
from config import Config
import os


class EmbeddingEngine:

    def __init__(self):
        print("Initializing Gemini Embedding Engine...")
        
        api_key = Config.GEMINI_API_KEY
        if not api_key:
            # Try loading from os.getenv as fallback
            api_key = os.getenv("GEMINI_API_KEY")
            
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing. Please set it in your environment.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = "text-embedding-004"
        print("Embedding Engine Ready")

    def create_embedding(self, text):
        # We need to make sure text is a string
        if not isinstance(text, str):
            text = str(text)
            
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text
        )
        return response.embeddings[0].values

    def create_embeddings(self, chunks):
        embedded_chunks = []
        total = len(chunks)

        for index, chunk in enumerate(chunks):
            print(f"Embedding {index + 1}/{total}")
            chunk["embedding"] = self.create_embedding(chunk["text"])
            embedded_chunks.append(chunk)

        return embedded_chunks