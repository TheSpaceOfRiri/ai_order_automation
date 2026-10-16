"""PDF text extraction.

Thin wrapper around pdfplumber. When the PDF's Bengali text layer is broken
(a real problem with the order PDFs), it can optionally fall back to OCR for
correct Bengali — enabled via config `pdf.use_ocr`.
"""
from __future__ import annotations

import logging
import re

import pdfplumber

from .ocr_reader import OCRReader, OCRUnavailable

logger = logging.getLogger(__name__)

# Bengali Unicode block. Real Bengali text has these; mojibake often does too,
# so we only use this to decide whether OCR is worth attempting.
_BENGALI_RE = re.compile(r"[ঀ-৿]")


class PDFReader:
    def __init__(self, use_ocr: bool = False, ocr_lang: str = "ben+eng"):
        self.use_ocr = use_ocr
        self.ocr = OCRReader(lang=ocr_lang)

    def extract_text(self, file_path: str) -> str:
        """Return all text in the PDF.

        If `use_ocr` is on AND the document contains Bengali, OCR is preferred
        (the embedded Bengali text layer is unreliable). Falls back to the
        plain text layer if OCR is unavailable.
        """
        plain = self._extract_plain(file_path)

        if self.use_ocr and _BENGALI_RE.search(plain):
            try:
                if self.ocr.available():
                    logger.info("Using OCR for Bengali-containing PDF.")
                    return self.ocr.extract_text(file_path)
                logger.warning("use_ocr set but OCR libs unavailable; using text layer.")
            except OCRUnavailable as exc:
                logger.warning("OCR unavailable (%s); using text layer.", exc)

        return plain

    def _extract_plain(self, file_path: str) -> str:
        logger.info("Reading PDF text layer: %s", file_path)
        chunks: list[str] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    logger.debug("Page %d: %d chars", i, len(text))
                    chunks.append(text)
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to read PDF '{file_path}': {exc}") from exc

        full_text = "\n".join(chunks)
        if not full_text.strip():
            logger.warning("PDF produced no extractable text (scanned image?).")
        return full_text
