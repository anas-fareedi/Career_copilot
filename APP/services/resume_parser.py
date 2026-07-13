"""
Resume parsing service.

Extracts plain text from PDF bytes using pypdf.
Centralised here so both the API upload route and agents can reuse it.
"""

import logging
from io import BytesIO

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """
    Extract and return all text from a PDF file's raw bytes.

    Returns an empty string if the PDF is unreadable (encrypted, corrupted, etc.)
    rather than raising — callers should validate that the result is non-empty.
    """
    try:
        reader = PdfReader(BytesIO(pdf_content))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages_text)
    except Exception as exc:
        logger.warning("Failed to extract text from PDF: %s", exc)
        return ""
