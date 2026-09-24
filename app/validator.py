from __future__ import annotations

from math import isclose

from .normalizer import normalize_contract, normalize_request, normalize_rig, normalize_well
from .schemas import InvoiceData, ValidationResult

MONEY_TOLERANCE = 0.01
DISCOUNT_TOLERANCE = 0.99


def _eq(a, b, tolerance=MONEY_TOLERANCE):
    if a is None or b is None:
        return None
    return isclose(float(a), float(b), abs_tol=tolerance, rel_tol=0.0)


def _eq_str(a, b):
    if a is None or b is None:
        return None
    return str(a).strip().upper() == str(b).strip().upper()


def _request_match(a, b):
    if a is None or b is None:
        return None
    return normalize_request(a) == normalize_request(b)


def _contract_match(a, b):
    if a is None or b is None:
        return None
    return normalize_contract(a) == normalize_contract(b)


def _rig_match(a, b):
    if a is None or b is None:
        return None
    return normalize_rig(a) == normalize_rig(b)


def _well_match(a, b):
    if a is None or b is None:
        return None
    return normalize_well(a) == normalize_well(b)


def get_discount_rate(contract_no, discount_rates: dict | None):
    if contract_no is None or discount_rates is None:
        return None
    contract_no = normalize_contract(contract_no)
    if not contract_no:
        return None
    rate = discount_rates.get(contract_no)
    return None if rate is None else float(rate)


def validate(
    accounting: InvoiceData,
    jst: InvoiceData,
    discount_rates: dict,
    custom_discount_rate: float | None = None,
):
    reasons: list[str] = []

    request_match = _request_match(accounting.request_number, jst.request_number)
    drss_match = _request_match(accounting.drss_number, jst.drss_number)

    # SOP uses Job ID from the JST. If Accounting independently contains a Job ID,
    # compare it; otherwise a successfully extracted JST Job ID is sufficient.
    if jst.job_number is None:
        job_id_match = None
        reasons.append("Job ID could not be extracted from the JST.")
    elif accounting.job_number is None:
        job_id_match = True
    else:
        job_id_match = _eq_str(accounting.job_number, jst.job_number)
        if job_id_match is False:
            reasons.append("Job ID mismatch.")

    well_match = _well_match(accounting.well_name, jst.well_name)
    rig_short_name_match = _rig_match(accounting.rig_short_name, jst.rig_short_name)
    contract_match = _contract_match(accounting.contract_no, jst.contract_no)

    accounting_total = accounting.grand_total_after_discount
    jst_total = jst.grand_total_after_discount or jst.total_after_discount
    total_amount_match = _eq(accounting_total, jst_total)

    # A custom rate applies only to this validation run. It never changes the
    # contract master/reference data.
    if custom_discount_rate is not None:
        expected_discount_percent = float(custom_discount_rate)
        discount_rate_source = "CUSTOM"
    else:
        expected_discount_percent = get_discount_rate(accounting.contract_no, discount_rates)
        discount_rate_source = "CONTRACT_MASTER"
    discount_percent_match = None
    discount_amount_match = None

    if expected_discount_percent is None:
        reasons.append(f"No discount rate configured for Contract No. {accounting.contract_no}.")
    elif jst.grand_total_before_discount is not None and jst.discount_amount is not None:
        expected_discount_amount = round(
            jst.grand_total_before_discount * expected_discount_percent / 100, 2
        )
        discount_difference = abs(float(jst.discount_amount) - float(expected_discount_amount))

        # A discrepancy up to SAR 0.99 is tolerated for validation purposes.
        # However, every non-zero discrepancy is reported so the tester/user can
        # see even a small mismatch. A difference of SAR 1.00 or more fails the
        # discount validation.
        discount_percent_match = discount_difference <= DISCOUNT_TOLERANCE
        discount_amount_match = discount_percent_match

        if discount_difference > 0:
            reasons.append(
                f"Discount discrepancy detected: JST discount is {jst.discount_amount:.2f} SAR, "
                f"expected {expected_discount_amount:.2f} SAR, "
                f"difference is {discount_difference:.2f} SAR."
            )

        if discount_difference > DISCOUNT_TOLERANCE:
            reasons.append(
                f"Discount difference exceeds the allowed tolerance of "
                f"SAR {DISCOUNT_TOLERANCE:.2f}."
            )
    else:
        reasons.append("Insufficient JST financial data to verify the predefined discount.")

    total_after_discount_match = None
    if (
        jst.grand_total_before_discount is not None
        and jst.discount_amount is not None
        and jst.grand_total_after_discount is not None
    ):
        calculated_total = round(
            jst.grand_total_before_discount - jst.discount_amount, 2
        )
        total_after_discount_match = _eq(
            calculated_total, jst.grand_total_after_discount
        )
        if not total_after_discount_match:
            reasons.append(
                f"JST total calculation is incorrect: "
                f"{jst.grand_total_before_discount:.2f} - {jst.discount_amount:.2f} "
                f"= {calculated_total:.2f}, but document shows "
                f"{jst.grand_total_after_discount:.2f}."
            )

    if request_match is False:
        reasons.append("Request Number mismatch.")
    if drss_match is False:
        reasons.append("DRSS Number mismatch.")
    if well_match is False:
        reasons.append("Well Name mismatch.")
    if rig_short_name_match is False:
        reasons.append("Rig Short Name mismatch.")
    if contract_match is False:
        reasons.append("Contract Number mismatch.")
    if total_amount_match is False:
        reasons.append("Total after discount does not match between documents.")

    checks = [
        request_match,
        drss_match,
        job_id_match,
        well_match,
        rig_short_name_match,
        contract_match,
        total_amount_match,
        discount_percent_match,
        total_after_discount_match,
    ]

    if any(check is None for check in checks):
        status = "REVIEW"
    elif all(check is True for check in checks):
        status = "VALID"
    else:
        status = "INVALID"

    return ValidationResult(
        status=status,
        request_match=request_match,
        drss_match=drss_match,
        job_id_match=job_id_match,
        well_match=well_match,
        rig_short_name_match=rig_short_name_match,
        contract_match=contract_match,
        total_amount_match=total_amount_match,
        discount_percent_match=discount_percent_match,
        discount_amount_match=discount_amount_match,
        total_after_discount_match=total_after_discount_match,
        reasons=reasons,
        accounting=accounting,
        jst=jst,
        discount_rate_used=expected_discount_percent,
        discount_rate_source=discount_rate_source,
        reference={
            "contract_no": accounting.contract_no,
            "expected_discount_percent": expected_discount_percent,
            "discount_rate_source": discount_rate_source,
        },
    )
