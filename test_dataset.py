from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.main import load_discount_rates
from app.extractor import detect_document_type, extract_fields
from app.ocr import ocr_pdf
from app.validator import validate


SAMPLES = ROOT / "samples"
OUTPUT = ROOT / "dataset_results.csv"


def run_case(case_dir: Path, rates: dict) -> dict:
    accounting_pdf = case_dir / "accounting.pdf"
    jst_pdf = case_dir / "jst.pdf"

    if not accounting_pdf.exists() or not jst_pdf.exists():
        return {"case": case_dir.name, "status": "SKIPPED", "reason": "Missing accounting.pdf or jst.pdf"}

    accounting_pages = ocr_pdf(accounting_pdf)
    jst_pages = ocr_pdf(jst_pdf)

    if detect_document_type(accounting_pages) != "accounting":
        return {"case": case_dir.name, "status": "ERROR", "reason": "Accounting document not detected"}
    if detect_document_type(jst_pages) != "jst":
        return {"case": case_dir.name, "status": "ERROR", "reason": "JST document not detected"}

    accounting = extract_fields(accounting_pages, "accounting")
    jst = extract_fields(jst_pages, "jst")
    result = validate(accounting, jst, rates)

    return {
        "case": case_dir.name,
        "status": result.status,
        "request": result.request_match,
        "drss": result.drss_match,
        "job_id": result.job_id_match,
        "well": result.well_match,
        "rig": result.rig_short_name_match,
        "contract": result.contract_match,
        "total": result.total_amount_match,
        "discount": result.discount_percent_match,
        "calculation": result.total_after_discount_match,
        "accounting_total": accounting.grand_total_after_discount,
        "jst_total": jst.grand_total_after_discount,
        "jst_discount": jst.discount_amount,
        "reasons": " | ".join(result.reasons),
    }


def main():
    rates = load_discount_rates(ROOT / "data" / "mock_erp.json")
    case_dirs = sorted(p for p in SAMPLES.iterdir() if p.is_dir())
    results = [run_case(case_dir, rates) for case_dir in case_dirs]

    if not results:
        print("No dataset cases found. Add samples/<case_name>/accounting.pdf and jst.pdf")
        return

    fields = list(results[0].keys())
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDataset results written to: {OUTPUT}")
    print("-" * 110)
    print(f"{'CASE':<16}{'STATUS':<12}{'REQUEST':<10}{'DRSS':<10}{'JOB ID':<10}{'WELL':<10}{'RIG':<10}{'CONTRACT':<10}{'TOTAL':<10}{'DISCOUNT':<10}")
    print("-" * 110)
    for r in results:
        print(
            f"{r['case']:<16}{r['status']:<12}{str(r.get('request')):<10}{str(r.get('drss')):<10}"
            f"{str(r.get('job_id')):<10}{str(r.get('well')):<10}{str(r.get('rig')):<10}"
            f"{str(r.get('contract')):<10}{str(r.get('total')):<10}{str(r.get('discount')):<10}"
        )


if __name__ == "__main__":
    main()
