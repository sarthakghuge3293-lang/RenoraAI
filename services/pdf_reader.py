import fitz
import os
from typing import List, Dict


class PDFReader:

    def __init__(self):
        pass

    def read_pdf(self, pdf_path: str) -> List[Dict]:

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(pdf_path)

        pdf_data = []

        try:

            for page_index in range(doc.page_count):

                page = doc.load_page(page_index)

                text = page.get_text("text")

                if text:
                    text = text.strip()
                else:
                    text = ""

                pdf_data.append({

                    "page": page_index + 1,

                    "text": text,

                    "word_count": len(text.split()),

                    "char_count": len(text)

                })

        finally:

            doc.close()

        return pdf_data