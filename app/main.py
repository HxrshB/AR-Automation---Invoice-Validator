from __future__ import annotations

import json
from pathlib import Path

from .extractor import detect_document_type, extract_fields
from .ocr import ocr_pdf
from .validator import validate


def load_discount_rates(path: str | Path = "data/mock_erp.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): float(v) for k, v in data.get("discount_rates", {}).items()}


def process_documents(
    accounting_pdf: str | Path,
    jst_pdf: str | Path,
    rates_path="data/mock_erp.json",
    custom_discount_rate: float | None = None,
):
    accounting_pages = ocr_pdf(accounting_pdf)
    jst_pages = ocr_pdf(jst_pdf)

    if detect_document_type(accounting_pages) != "accounting":
        raise ValueError("The Accounting PDF does not appear to be an Accounting Information document.")
    if detect_document_type(jst_pages) != "jst":
        raise ValueError("The JST PDF does not appear to be a Job Service Ticket / Service Report document.")

    accounting = extract_fields(accounting_pages, "accounting")
    jst = extract_fields(jst_pages, "jst")
    rates = load_discount_rates(rates_path)
    return validate(accounting, jst, rates, custom_discount_rate=custom_discount_rate)
