"""Shared test fixtures: small synthetic PDFs (no external corpus needed)."""
from __future__ import annotations

from pathlib import Path

import pymupdf


def make_text_pdf(path, pages: int = 2) -> Path:
    """Write a small native-text PDF (headings + prose paragraphs)."""
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Page {i + 1} heading", fontsize=14)
        for j, line in enumerate([
            "The quick brown fox jumps over the lazy dog.",
            "Adaptive layout engine extracts this paragraph cleanly.",
            "Second paragraph with more words to wrap across the line.",
        ]):
            page.insert_text((72, 140 + j * 18), line, fontsize=11)
    doc.save(str(path))
    doc.close()
    return Path(path)
