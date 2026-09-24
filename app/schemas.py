from typing import Optional
from pydantic import BaseModel, Field


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    request_number: Optional[str] = None
    drss_number: Optional[str] = None
    job_number: Optional[str] = None
    jst_number: Optional[str] = None
    well_name: Optional[str] = None
    rig_short_name: Optional[str] = None
    rig_number: Optional[str] = None
    contract_no: Optional[str] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    discount_percent: Optional[float] = None
    discount_amount: Optional[float] = None
    total_after_discount: Optional[float] = None
    subtotal: Optional[float] = None
    grand_total_before_discount: Optional[float] = None
    grand_total_after_discount: Optional[float] = None
    receiver_discount_amount: Optional[float] = None
    raw_text_pages: dict[int, str] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    status: str
    request_match: Optional[bool] = None
    drss_match: Optional[bool] = None
    job_id_match: Optional[bool] = None
    well_match: Optional[bool] = None
    rig_short_name_match: Optional[bool] = None
    contract_match: Optional[bool] = None
    total_amount_match: Optional[bool] = None
    discount_percent_match: Optional[bool] = None
    discount_amount_match: Optional[bool] = None
    total_after_discount_match: Optional[bool] = None
    discount_rate_used: Optional[float] = None
    discount_rate_source: Optional[str] = None
    reasons: list[str] = Field(default_factory=list)
    accounting: InvoiceData
    jst: InvoiceData
    reference: dict = Field(default_factory=dict)
