"""
services/pdf_reader.py
───────────────────────
Enhanced PDF reader using PyMuPDF (fitz).

Improvements over v1:
- Reads ALL pages (unchanged ✅)
- Extracts tables accurately via fitz table API (unchanged ✅)
- Preserves heading structure using font-size heuristics (NEW)
- Maintains document hierarchy (NEW)
- OCR fallback for scanned pages with < 50 chars of text (NEW — uses pytesseract if available)
- Never skips pages — marks low-text pages as [SCANNED_PAGE] (NEW)
"""

import os
import fitz  # PyMuPDF
from typing import List, Dict

# OCR is optional — gracefully degrade if pytesseract/Pillow not installed
try:
    import pytesseract
    from PIL import Image
    import io
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


class PDFReader:

    # Pages with fewer characters than this trigger OCR fallback
    OCR_THRESHOLD = 50

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
                page_dict = self._read_page(page, page_index + 1)
                pdf_data.append(page_dict)
        finally:
            doc.close()

        return pdf_data

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _read_page(self, page: fitz.Page, page_num: int) -> Dict:
        """Extract all content from a single PDF page."""

        # 1. Extract structured text (preserves headings via font size)
        main_text = self._extract_structured_text(page)

        # 2. Extract tables
        table_text = self._extract_tables(page)

        # 3. Combine
        combined = main_text.strip()
        if table_text:
            combined += f"\n\n[TABLES]\n{table_text}"

        # 4. OCR fallback for scanned pages
        if len(combined.strip()) < self.OCR_THRESHOLD:
            ocr_text = self._ocr_page(page, page_num)
            if ocr_text:
                combined = ocr_text
            else:
                combined = f"[SCANNED_PAGE: page {page_num} — text extraction failed. Consider uploading a text-based PDF.]"

        return {
            "page": page_num,
            "text": combined.strip(),
            "word_count": len(combined.split()),
            "char_count": len(combined),
        }

    def _extract_structured_text(self, page: fitz.Page) -> str:
        """
        Extract text preserving heading hierarchy using font size.
        Large font → heading prefix (##), medium → subheading (#), rest → body.
        """
        try:
            # Get all text spans with font info
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])

            # Collect all unique font sizes to detect headings
            all_sizes = []
            for block in blocks:
                if block.get("type") != 0:  # type 0 = text
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0)
                        if size > 0:
                            all_sizes.append(size)

            # Determine heading thresholds
            if all_sizes:
                max_size = max(all_sizes)
                body_size = sorted(all_sizes)[len(all_sizes) // 2]  # median = body text
                heading_threshold = max(body_size * 1.2, body_size + 2)
                big_heading_threshold = max(body_size * 1.5, body_size + 4)
            else:
                heading_threshold = 14
                big_heading_threshold = 18

            lines_output = []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_text_parts = []
                    max_span_size = 0
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        size = span.get("size", 0)
                        if text:
                            line_text_parts.append(text)
                            max_span_size = max(max_span_size, size)

                    line_text = " ".join(line_text_parts).strip()
                    if not line_text:
                        continue

                    # Add heading markers for structure
                    if max_span_size >= big_heading_threshold:
                        lines_output.append(f"\n## {line_text}\n")
                    elif max_span_size >= heading_threshold:
                        lines_output.append(f"\n# {line_text}\n")
                    else:
                        lines_output.append(line_text)

            return "\n".join(lines_output)

        except Exception as e:
            print(f"[PDFReader] Structured text extraction error: {e}")
            # Fallback to simple text extraction
            return page.get_text("text") or ""

    def _extract_tables(self, page: fitz.Page) -> str:
        """Extract tables from the page as pipe-separated rows."""
        table_text = ""
        try:
            tables = page.find_tables()
            for table in tables:
                table_data = table.extract()
                for row in table_data:
                    clean_row = [
                        str(cell).strip().replace("\n", " ") if cell is not None else ""
                        for cell in row
                    ]
                    table_text += " | ".join(clean_row) + "\n"
                table_text += "\n"
        except Exception as e:
            print(f"[PDFReader] Table extraction error: {e}")
        return table_text

    def _ocr_page(self, page: fitz.Page, page_num: int) -> str:
        """
        OCR fallback for scanned pages.
        Renders the page to an image and runs pytesseract.
        Returns extracted text or empty string if OCR unavailable.
        """
        if not _OCR_AVAILABLE:
            print(f"[PDFReader] Page {page_num} is likely scanned. Install pytesseract + Pillow for OCR support.")
            return ""

        try:
            # Render at 2x resolution for better OCR accuracy
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img_data = pix.tobytes("png")

            image = Image.open(io.BytesIO(img_data))
            ocr_text = pytesseract.image_to_string(image, lang="eng")
            print(f"[PDFReader] OCR completed for page {page_num} ({len(ocr_text)} chars)")
            return ocr_text.strip()
        except Exception as e:
            print(f"[PDFReader] OCR error on page {page_num}: {e}")
            return ""