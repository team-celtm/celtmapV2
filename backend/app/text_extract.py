from __future__ import annotations

from io import BytesIO

from docx import Document
from pypdf import PdfReader


def extract_text_from_bytes(filename: str, content: bytes) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        chunks = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(chunks).strip()
    if lowered.endswith(".docx"):
        document = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    try:
        return content.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""
