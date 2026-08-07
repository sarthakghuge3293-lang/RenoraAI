"""
services/chunker.py
────────────────────
Semantic-aware text chunker.

Improvements over v1:
- Splits on paragraph boundaries (\\n\\n) first — never cuts mid-sentence
- Merges short paragraphs up to chunk_size to avoid tiny useless chunks
- Preserves TABLE blocks intact — never splits a table across chunks
- Carries over section_heading metadata per chunk for better retrieval context
- Falls back to character-level splitting only for very long single paragraphs
"""

import uuid
import re
from typing import List, Dict


class TextChunker:

    def __init__(self, chunk_size: int = 1200, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def chunk_document(self, doc_name: str, pages: List[Dict]) -> List[Dict]:
        """
        Takes the list of page dicts from the document reader and returns
        a flat list of chunk dicts ready for embedding.
        """
        chunks = []
        for page in pages:
            text = page.get("text", "").strip()
            page_num = page.get("page", 1)
            if not text:
                continue
            page_chunks = self._chunk_page(text, doc_name, page_num)
            chunks.extend(page_chunks)
        return chunks

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _chunk_page(self, text: str, doc_name: str, page_num: int) -> List[Dict]:
        """Split a single page's text into semantically coherent chunks."""
        # Separate any TABLE blocks — keep them intact
        table_blocks, clean_text = self._extract_tables(text)

        chunks = []
        current_heading = ""

        # Split remaining text into paragraphs
        paragraphs = re.split(r"\n{2,}", clean_text)

        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Detect headings (short lines in ALL CAPS or ending with ':')
            if self._is_heading(para):
                # If we have accumulated content, flush it as a chunk
                if current_chunk.strip():
                    chunks.append(self._make_chunk(
                        current_chunk.strip(), doc_name, page_num, current_heading
                    ))
                    current_chunk = ""
                current_heading = para

            # If this paragraph would overflow the chunk, flush first
            if len(current_chunk) + len(para) + 2 > self.chunk_size:
                if current_chunk.strip():
                    chunks.append(self._make_chunk(
                        current_chunk.strip(), doc_name, page_num, current_heading
                    ))
                # If the paragraph itself is huge, split it by sentences
                if len(para) > self.chunk_size:
                    for sub in self._split_large_paragraph(para):
                        chunks.append(self._make_chunk(
                            sub, doc_name, page_num, current_heading
                        ))
                    current_chunk = ""
                else:
                    current_chunk = para + "\n\n"
            else:
                current_chunk += para + "\n\n"

        # Flush remaining
        if current_chunk.strip():
            chunks.append(self._make_chunk(
                current_chunk.strip(), doc_name, page_num, current_heading
            ))

        # Add table blocks as separate chunks (never split)
        for table_text in table_blocks:
            if table_text.strip():
                chunks.append(self._make_chunk(
                    table_text.strip(), doc_name, page_num,
                    current_heading, is_table=True
                ))

        return chunks

    def _extract_tables(self, text: str):
        """
        Separates [TABLES] blocks from normal text.
        Returns (list_of_table_strings, remaining_text).
        """
        table_pattern = re.compile(r"\[TABLES\](.*?)(?=\[TABLES\]|$)", re.DOTALL)
        tables = table_pattern.findall(text)
        clean = table_pattern.sub("", text).strip()
        return tables, clean

    def _is_heading(self, text: str) -> bool:
        """Heuristic: short all-caps line OR ends with ':' and is short."""
        stripped = text.strip()
        if len(stripped) > 100:
            return False
        if stripped.isupper() and len(stripped.split()) <= 10:
            return True
        if stripped.endswith(":") and len(stripped.split()) <= 8:
            return True
        return False

    def _split_large_paragraph(self, text: str) -> List[str]:
        """Split a very long paragraph by sentence boundaries with overlap."""
        # Split by sentence-ending punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current = ""
        for sent in sentences:
            if len(current) + len(sent) + 1 > self.chunk_size:
                if current.strip():
                    chunks.append(current.strip())
                # Start new chunk with overlap from previous
                overlap_text = current[-self.overlap:] if len(current) > self.overlap else current
                current = overlap_text + " " + sent
            else:
                current += " " + sent
        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _make_chunk(self, text: str, doc_name: str, page: int,
                    section_heading: str = "", is_table: bool = False) -> Dict:
        prefix = f"[{section_heading}]\n" if section_heading else ""
        full_text = prefix + text

        return {
            "chunk_id": str(uuid.uuid4()),
            "pdf_name": doc_name,
            "page": page,
            "text": full_text,
            "section_heading": section_heading,
            "is_table": is_table,
            "char_start": 0,
            "char_end": len(full_text),
        }