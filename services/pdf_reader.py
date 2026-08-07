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

                # Extract tables
                table_text = ""
                try:
                    tables = page.find_tables()
                    for table in tables:
                        table_data = table.extract()
                        for row in table_data:
                            # Filter out None values
                            clean_row = [str(cell).strip().replace('\n', ' ') if cell is not None else "" for cell in row]
                            table_text += " | ".join(clean_row) + "\n"
                        table_text += "\n"
                except Exception as e:
                    print("Table extraction error:", e)

                # Extract blocks
                blocks = page.get_text("blocks")
                text_blocks = []
                for b in blocks:
                    if len(b) >= 5 and isinstance(b[4], str) and b[4].strip():
                        text_blocks.append(b[4].strip())

                text = "\n\n".join(text_blocks)
                
                if table_text:
                    text += "\n\n[TABLES]\n" + table_text

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