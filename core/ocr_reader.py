"""Optional OCR-based PDF reader for correct Bengali extraction.

WHY THIS EXISTS
    The order PDFs embed Bengali with a broken font/ToUnicode mapping, so the
    normal text layer comes out as mojibake (e.g. "মোঃ শামিম" -> "জমাোঃ শারমম").
    The *pixels* are correct, though, so rendering each page to an image and
    running Bengali OCR recovers the real text.

REQUIREMENTS (install only if you need Bengali):
    pip install pytesseract pdf2image
    # System packages:
    #   Tesseract OCR + Bengali data:  `tesseract-ocr` and `tesseract-ocr-ben`
    #   Poppler (for pdf2image):       `poppler-utils`

USAGE
    Enabled via config: "pdf": { "use_ocr": true, "ocr_lang": "ben+eng" }.
    If the OCR libraries are missing, this raises OCRUnavailable and the caller
    falls back to the normal text layer.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class OCRUnavailable(RuntimeError):
    """Raised when OCR dependencies are not installed."""


class OCRReader:
    def __init__(self, lang: str = "ben+eng", dpi: int = 300):
        self.lang = lang
        self.dpi = dpi

    def available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            import pdf2image    # noqa: F401
            return True
        except Exception:
            return False

    def extract_text(self, file_path: str) -> str:
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except Exception as exc:  # pragma: no cover - depends on environment
            raise OCRUnavailable(
                "OCR requires 'pytesseract' + 'pdf2image' (and system Tesseract "
                "with the Bengali language pack). Install them or disable use_ocr."
            ) from exc

        logger.info("OCR reading (lang=%s, dpi=%d): %s", self.lang, self.dpi, file_path)
        pages = convert_from_path(file_path, dpi=self.dpi)
        chunks = []
        for i, img in enumerate(pages, start=1):
            text = pytesseract.image_to_string(img, lang=self.lang)
            logger.debug("OCR page %d: %d chars", i, len(text))
            chunks.append(text)
        return "\n".join(chunks)
