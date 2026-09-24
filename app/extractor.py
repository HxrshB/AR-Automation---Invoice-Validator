from __future__ import annotations

import re
from typing import Optional

from .normalizer import normalize_contract, normalize_request
from .schemas import InvoiceData


NUMBER = r"-?[\d,]+(?:\.\d+)?"


def _all_text(pages: dict[int, str]) -> str:
    return "\n".join(pages.get(k, "") for k in sorted(pages))


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _first_match(patterns: list[str], text: str, flags=re.I) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip()
    return None


def _number(value: str | None) -> Optional[float]:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _next_nonempty(lines: list[str], index: int, limit: int = 5) -> Optional[str]:
    seen = 0
    for j in range(index + 1, min(len(lines), index + 1 + limit)):
        candidate = lines[j].strip()
        if candidate:
            seen += 1
            if seen == 1:
                return candidate
    return None


def _label_value(text: str, labels: list[str], value_pattern: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines()]
    for i, line in enumerate(lines):
        for label in labels:
            if re.search(label, line, re.I):
                inline = re.search(label + r"\s*[:#]?\s*" + value_pattern, line, re.I)
                if inline:
                    return inline.group(1).strip()
                nxt = _next_nonempty(lines, i)
                if nxt:
                    match = re.search(r"^" + value_pattern + r"$", nxt, re.I)
                    if match:
                        return match.group(1).strip()
    return None

def _find_page_containing(pages: dict[int, str], *terms: str) -> str:
    for text in pages.values():
        if all(re.search(re.escape(term), text, re.I) for term in terms):
            return text
    return ""


def _extract_request(text: str) -> Optional[str]:
    value = _label_value(text, [r"Request\s*Number", r"DRSS"], r"(300\s*\d{7})")
    if value is None:
        value = _first_match([r"\b(300\d{7})\b"], text)
    return normalize_request(value)


def _extract_drss(text: str) -> Optional[str]:
    value = _label_value(text, [r"DRSS", r"Ref\s*DRSS"], r"(300\s*\d{7})")
    return normalize_request(value)


def _extract_contract(text: str) -> Optional[str]:
    value = _label_value(text, [r"Contract\s*(?:No\.?|Number|#)"], r"(\d{10})")
    if value is None:
        value = _first_match([r"\b(66\d{8})\b"], text)
    return normalize_contract(value)


def _extract_well(text: str) -> Optional[str]:
    patterns = [
        r"Well\s*Name\s*[:#]?\s*([A-Z]{2,}[\- ]\d{2,5})",
        r"([A-Z]{2,}[\- ]\d{2,5})\s*\n?Well\s*Name",
        r"Well\s+([A-Z]{2,}[\- ]\d{2,5})",
        r"Well\s*Name\s*/\s*Number\s*.*?\b([A-Z]{2,}[\- ]\d{2,5})\b",
    ]
    value = _first_match(patterns, text)
    return value


def _extract_rig(text: str) -> Optional[str]:
    patterns = [
        r"Rig\s*Short\s*Name\s*[:#]?\s*([A-Z0-9]+[\- ]?[A-Z0-9]+)",
        r"([A-Z0-9]+[\- ]?[A-Z0-9]+)\s*\n?Rig\s*Short\s*Name",
        r"Rig\s+([A-Z]{2,}[- ]\d{2,5})\s+TIME\s+CALCULATION",
        r"Rig\s*No\.?\s*[:#]?\s*([A-Z]{2,}[- ]\d{2,5})",
    ]
    return _first_match(patterns, text)

def _extract_job_id(text: str) -> Optional[str]:
    compact = _compact(text)
    value = _first_match([
        r"Job\s*ID\s*[:#]?\s*(?:Country\s+)?[^0-9]{0,40}(\d{5})\b",
        r"Job\s*ID\s*[:#]?\s*(\d{5,})",
    ], compact)
    return value


def _extract_currency(text: str) -> Optional[str]:
    if re.search(r"\bSAR\b|Saudi\s+Arabian\s+Riyal", text, re.I):
        return "SAR"
    if re.search(r"\bUSD\b", text, re.I):
        return "USD"
    return None


def _financial_block_accounting(pages: dict[int, str]) -> str:
    # Financial summary is normally on the final populated page.
    for page_no in sorted(pages, reverse=True):
        text = pages[page_no]
        if re.search(r"Grand\s+Total\s+before\s+Discount", text, re.I):
            return text
    return _all_text(pages)


def _financial_block_jst(pages: dict[int, str]) -> str:
    for page_no in sorted(pages):
        text = pages[page_no]
        if re.search(r"SUB\s*[- ]?TOTAL", text, re.I) and re.search(r"DISCOUNT", text, re.I) and re.search(r"TOTAL", text, re.I):
            return text
    return _all_text(pages)


def _scan_exact_label_after(text: str, label: str, limit: int = 5) -> Optional[float]:
    lines = [line.strip() for line in text.splitlines()]
    for i, line in enumerate(lines):
        if re.fullmatch(label, line, re.I):
            inline = re.search(rf"^({NUMBER})$", line, re.I)
            if inline:
                return _number(inline.group(1))
            for j in range(i + 1, min(len(lines), i + 1 + limit)):
                m = re.fullmatch(rf"({NUMBER})", lines[j], re.I)
                if m:
                    return _number(m.group(1))
    return None


def _scan_number_before_label(text: str, label: str, limit: int = 4) -> Optional[float]:
    lines = [line.strip() for line in text.splitlines()]
    for i, line in enumerate(lines):
        if re.search(label, line, re.I):
            for j in range(i - 1, max(-1, i - limit - 1), -1):
                m = re.fullmatch(rf"({NUMBER})", lines[j], re.I)
                if m:
                    return _number(m.group(1))
    return None


def _extract_accounting_financials(pages: dict[int, str]) -> dict[str, Optional[float]]:
    text = _financial_block_accounting(pages)
    discount = _scan_number_before_label(text, r"Total\s+Discount.*")
    if discount is None:
        m = re.search(r"Total\s+Discount\s*:\s*[\d.]+\s*%\s*({})".format(NUMBER), text, re.I)
        if m:
            discount = _number(m.group(1))
    return {
        "before": _scan_number_before_label(text, r"Grand\s+Total\s+before\s+Discount"),
        "discount": discount,
        "after": _scan_number_before_label(text, r"Grand\s+Total\s+after\s+Discount"),
    }


def _extract_jst_financials(pages: dict[int, str]) -> dict[str, Optional[float]]:
    text = _financial_block_jst(pages)
    return {
        "before": _scan_exact_label_after(text, r"SUB\s*-\s*TOTAL"),
        "discount": _scan_exact_label_after(text, r"DISCOUNT"),
        "after": _scan_exact_label_after(text, r"TOTAL"),
    }

def extract_accounting_fields(pages: dict[int, str]) -> InvoiceData:
    header = pages.get(1, _all_text(pages))
    financials = _extract_accounting_financials(pages)

    request = _first_match([r"(300\d{7})\s*\n?Request\s*Number", r"Request\s*Number\s*[:#]?\s*(300\d{7})"], header)
    request = normalize_request(request)
    drss = _first_match([r"DRSS\s*[:#]?\s*(300\d{7})", r"(300\d{7})\s*\n?Ref\s*DRSS"], header) or request
    drss = normalize_request(drss)
    well = _first_match([r"([A-Z]{2,}[\- ]\d{2,5})\s*\n?Well\s*Name\s*:", r"Well\s*Name\s*[:#]?\s*([A-Z]{2,}[\- ]\d{2,5})"], header)
    rig = _first_match([r"([A-Z0-9]+[\- ]?[A-Z0-9]+)\s*\n?Rig\s*Short\s*Name\s*:", r"Rig\s*Short\s*Name\s*[:#]?\s*([A-Z0-9]+[\- ]?[A-Z0-9]+)"], header)
    contract = _first_match([r"(66\d{8})\s*\n?Contract\s*No\s*:", r"Contract\s*No\s*[:#]?\s*(\d{10})"], header)
    contract = normalize_contract(contract)

    before = financials["before"]
    discount = financials["discount"]
    after = financials["after"]

    return InvoiceData(
        request_number=request,
        drss_number=drss,
        well_name=well,
        rig_short_name=rig,
        contract_no=contract,
        currency=_extract_currency(_all_text(pages)),
        total_amount=after,
        discount_amount=discount,
        total_after_discount=after,
        subtotal=before,
        grand_total_before_discount=before,
        grand_total_after_discount=after,
        raw_text_pages=pages,
    )


def extract_jst_fields(pages: dict[int, str]) -> InvoiceData:
    full = _all_text(pages)
    # Page 1 and the service-report summary page are both useful. Prefer pages
    # containing the explicit field labels, rather than searching every number.
    header = pages.get(1, "")
    summary = _find_page_containing(pages, "Client Request # or DRSS #", "Job ID")
    if not summary:
        summary = full

    summary_compact = _compact(summary)

    # Request / DRSS are header identifiers. They MUST come from page 1 only.
    # Do not fall back to later pages because those pages may contain other
    # 300XXXXXXXX references belonging to supporting records.
    request = _extract_request(header)
    drss = _extract_drss(header) or request

    contract = normalize_contract(_first_match([r"Client\s*PO\s*or\s*Contract\s*#.*?\b(66\d{8})\b"], summary_compact))
    job_id = _first_match([r"Job\s*ID.*?\b(\d{5})\b"], summary_compact)

    contract = contract or _extract_contract(header) or _extract_contract(full)
    well = _extract_well(header) or _extract_well(summary) or _extract_well(full)
    rig = _extract_rig(header) or _extract_rig(summary) or _extract_rig(full)
    job_id = job_id or _extract_job_id(summary) or _extract_job_id(full)

    financials = _extract_jst_financials(pages)
    before = financials["before"]
    discount = financials["discount"]
    after = financials["after"]

    return InvoiceData(
        request_number=request,
        drss_number=drss,
        job_number=job_id,
        jst_number=_first_match([r"Ticket\s*No\.?\s*[:#]?\s*([A-Z0-9\- ]+)", r"\b(CMT-\d{3,})\b"], header),
        well_name=well,
        rig_short_name=rig,
        contract_no=contract,
        currency=_extract_currency(full),
        total_amount=after,
        discount_amount=discount,
        total_after_discount=after,
        subtotal=before,
        grand_total_before_discount=before,
        grand_total_after_discount=after,
        raw_text_pages=pages,
    )


def extract_fields(pages: dict[int, str], document_type: str) -> InvoiceData:
    if document_type == "accounting":
        return extract_accounting_fields(pages)
    if document_type == "jst":
        return extract_jst_fields(pages)
    raise ValueError(f"Unknown document_type: {document_type}")


def detect_document_type(pages: dict[int, str]) -> Optional[str]:
    text = _all_text(pages)
    if re.search(r"ACCOUNTING\s+INFORMATION", text, re.I):
        return "accounting"
    if re.search(r"JOB\s+SERVICE\s+TICKET|KSU\s+CMT\s+SERVICE\s+REPORT|SERVICE\s+REPORT", text, re.I):
        return "jst"
    return None
