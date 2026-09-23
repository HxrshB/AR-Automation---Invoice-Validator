from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.extractor import detect_document_type, extract_fields
from app.ocr import ocr_pdf
from app.validator import validate


st.set_page_config(page_title="Invoice Discount Validator", page_icon="📄", layout="wide")
st.title("Invoice Discount Validator")
st.caption("Upload the Accounting Information PDF and the matching JST / Service Report PDF.")


def load_rates():
    with open(ROOT / "data" / "mock_erp.json", "r", encoding="utf-8") as f:
        return json.load(f)["discount_rates"]


def check_label(name: str, value):
    if value is True:
        return f"✓ {name}"
    if value is False:
        return f"✗ {name}"
    return f"⚠ {name} — Unable to verify"


def render_check(name: str, value):
    if value is True:
        st.success(check_label(name, value))
    elif value is False:
        st.error(check_label(name, value))
    else:
        st.warning(check_label(name, value))


def save_upload(uploaded, path: Path):
    path.write_bytes(uploaded.getbuffer())


accounting_file = st.file_uploader(
    "Accounting Information PDF", type=["pdf"], key="accounting"
)
jst_file = st.file_uploader(
    "JST / Service Report PDF", type=["pdf"], key="jst"
)

if st.button("Validate Documents", type="primary", use_container_width=True):
    if not accounting_file or not jst_file:
        st.error("Please upload both PDF documents.")
        st.stop()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        accounting_path = temp_dir / "accounting.pdf"
        jst_path = temp_dir / "jst.pdf"
        save_upload(accounting_file, accounting_path)
        save_upload(jst_file, jst_path)

        try:
            with st.spinner("Reading and validating documents..."):
                accounting_pages = ocr_pdf(accounting_path)
                jst_pages = ocr_pdf(jst_path)

                accounting_type = detect_document_type(accounting_pages)
                jst_type = detect_document_type(jst_pages)

                if accounting_type != "accounting":
                    raise ValueError("The first PDF does not look like an Accounting Information document.")
                if jst_type != "jst":
                    raise ValueError("The second PDF does not look like a JST / Service Report document.")

                accounting = extract_fields(accounting_pages, "accounting")
                jst = extract_fields(jst_pages, "jst")
                result = validate(accounting, jst, load_rates())

            st.divider()
            st.header("Validation Result")
            if result.status == "VALID":
                st.success("✓ INVOICE VALID")
            elif result.status == "INVALID":
                st.error("✗ INVOICE INVALID")
            else:
                st.warning("⚠ REVIEW REQUIRED")

            st.subheader("Validation Checks")
            checks = [
                ("Request Number", result.request_match),
                ("DRSS Number", result.drss_match),
                ("Job ID", result.job_id_match),
                ("Well Name", result.well_match),
                ("Rig Short Name", result.rig_short_name_match),
                ("Contract Number", result.contract_match),
                ("Total Amount", result.total_amount_match),
                ("Discount Rate / Amount", result.discount_percent_match),
                ("Final Total Calculation", result.total_after_discount_match),
            ]
            columns = st.columns(2)
            for index, (name, value) in enumerate(checks):
                with columns[index % 2]:
                    render_check(name, value)

            st.divider()
            st.subheader("Financial Verification")
            rate = result.reference.get("expected_discount_percent")
            before = result.jst.grand_total_before_discount
            expected = None if rate is None or before is None else round(before * rate / 100, 2)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Contract", result.reference.get("contract_no") or "Not extracted")
            c2.metric("Configured Discount", f"{rate:.2f}%" if rate is not None else "Not configured")
            c3.metric("Expected Discount", f"SAR {expected:,.2f}" if expected is not None else "Not available")
            c4.metric("JST Discount", f"SAR {result.jst.discount_amount:,.2f}" if result.jst.discount_amount is not None else "Not extracted")

            st.subheader("Invoice Totals")
            c1, c2 = st.columns(2)
            c1.metric("Accounting Total", f"SAR {result.accounting.grand_total_after_discount:,.2f}" if result.accounting.grand_total_after_discount is not None else "Not extracted")
            c2.metric("JST Total", f"SAR {result.jst.grand_total_after_discount:,.2f}" if result.jst.grand_total_after_discount is not None else "Not extracted")

            if result.reasons:
                st.subheader("Review Notes")
                for reason in result.reasons:
                    st.write(f"• {reason}")

            with st.expander("Extracted Accounting Information"):
                st.json(result.accounting.model_dump(exclude={"raw_text_pages"}))
            with st.expander("Extracted JST Information"):
                st.json(result.jst.model_dump(exclude={"raw_text_pages"}))
            with st.expander("OCR Text — Accounting"):
                for page, text in result.accounting.raw_text_pages.items():
                    st.markdown(f"**Page {page}**")
                    st.text(text)
            with st.expander("OCR Text — JST"):
                for page, text in result.jst.raw_text_pages.items():
                    st.markdown(f"**Page {page}**")
                    st.text(text)

        except Exception as exc:
            st.error(f"An error occurred while processing the documents:\n\n{exc}")
