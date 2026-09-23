from __future__ import annotations

import re
from typing import Optional


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value).strip()).upper()


def normalize_identifier(value: Optional[str]) -> Optional[str]:
    value = normalize_text(value)
    if value is None:
        return None
    return re.sub(r"[^A-Z0-9]", "", value)


def normalize_rig(value: Optional[str]) -> Optional[str]:
    """Normalize separator differences and the agreed trailing-S variation."""
    value = normalize_identifier(value)
    if value is None:
        return None
    if value.endswith("S"):
        value = value[:-1]
    return value


def normalize_well(value: Optional[str]) -> Optional[str]:
    """Normalize formatting and numeric zero-padding, but avoid fuzzy matching."""
    value = normalize_text(value)
    if value is None:
        return None
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^A-Z0-9\-]", "", value)

    match = re.fullmatch(r"([A-Z]+)-([0-9]+)", value)
    if match:
        prefix, number = match.groups()
        return f"{prefix}-{int(number)}"
    return value


def normalize_contract(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits or None


def normalize_request(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    match = re.search(r"300\d{7}", str(value).replace(" ", ""))
    return match.group(0) if match else re.sub(r"\D", "", str(value)) or None
