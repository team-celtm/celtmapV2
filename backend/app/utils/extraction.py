from __future__ import annotations

import io
from typing import Any

from pypdf import PdfReader
from docx import Document
from PIL import Image
#import pytesseract

def extract_text_from_bytes(content: bytes, file_name: str | None, file_type: str) -> str:
    """
    Extracts plain text from document bytes based on file type.
    Supported: pdf, docx, txt, images.
    """
    if not content:
        return ""

    fn_lower = (file_name or "").lower()
    ft_lower = (file_type or "").lower()
    
    is_image = False
    if "image/" in ft_lower:
        is_image = True
    elif any(fn_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]):
        is_image = True

    if is_image:
        return _extract_from_image(content)
    elif "pdf" in fn_lower or "pdf" in ft_lower:
        return _extract_from_pdf(content)
    elif "docx" in fn_lower or "officedocument" in ft_lower:
        return _extract_from_docx(content)
    else:
        # Assume text/plain or similar
        text = content.decode("utf-8", errors="ignore")
        return text.replace("\x00", "")

def _extract_from_image(content: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(content))
        # Preprocess: convert to grayscale
        image = image.convert("L")
        
        # Optional basic thresholding could be done here if needed
        # threshold = 200
        # image = image.point(lambda p: p > threshold and 255)

        #text = pytesseract.image_to_string(image)
        text = "OCR_DISABLED"
        
        # Sanitize extracted text
        # Remove null bytes and ensure valid UTF-8
        sanitized_text = text.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8")
        return sanitized_text.strip()
    except Exception as e:
        raise Exception(f"OCR extraction failed: {str(e)}")

def _extract_from_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            # Sanitize null bytes
            text.append(page_text.replace("\x00", ""))
    return "\n".join(text)

def _extract_from_docx(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    # Sanitize null bytes
    return "\n".join([para.text.replace("\x00", "") for para in doc.paragraphs])
