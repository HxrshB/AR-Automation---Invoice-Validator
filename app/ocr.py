from __future__ import annotations

from pathlib import Path
import re

import fitz
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


OCR_MIN_TEXT_LENGTH = 80
OCR_DPI = 300


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def _preprocess(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(1.4)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def _ocr_page(page) -> str:
    matrix = fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    image = _preprocess(image)

    outputs = []
    for psm in (6, 11):
        text = pytesseract.image_to_string(image, config=f"--oem 3 --psm {psm}")
        outputs.append(text)

    return max(outputs, key=lambda x: len(x.strip()), default="")


def ocr_pdf(pdf_path: str | Path) -> dict[int, str]:
    """Return one text string per PDF page.

    Native PDF text is preferred because many of these documents are generated
    electronically. OCR is used as a fallback for pages with little/no text.
    """
    pdf_path = Path(pdf_path)
    pages: dict[int, str] = {}

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            native = _clean_text(page.get_text("text"))
            if len(native) >= OCR_MIN_TEXT_LENGTH:
                pages[page_number] = native
            else:
                pages[page_number] = _clean_text(_ocr_page(page))

    return pages
