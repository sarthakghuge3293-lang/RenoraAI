import uuid


class TextChunker:

    def __init__(self,
                 chunk_size=1000,
                 overlap=200):

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self,
                       pdf_name,
                       pages):

        chunks = []

        for page in pages:

            text = page["text"]

            start = 0

            while start < len(text):

                end = start + self.chunk_size

                chunk_text = text[start:end]

                chunks.append({

                    "chunk_id": str(uuid.uuid4()),

                    "pdf_name": pdf_name,

                    "page": page["page"],

                    "text": chunk_text,

                    "char_start": start,

                    "char_end": end

                })

                start += self.chunk_size - self.overlap

        return chunks