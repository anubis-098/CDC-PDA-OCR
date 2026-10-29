from decimal import Decimal, InvalidOperation
from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["match", "mismatch", "unit_mismatch", "review"]
Kind = Literal["checking", "invoice"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    page: int = Field(ge=1)
    box: list[list[float]] = Field(default_factory=list)


class Item(StrictModel):
    code: str = Field(default="", max_length=100)
    qty: str = Field(default="", max_length=40)
    uom: str = Field(default="", max_length=20)
    source: str = ""
    confidence: float = Field(default=0, ge=0, le=1)


class Extracted(StrictModel):
    po: str = Field(default="", max_length=100)
    po_source: str = ""
    po_confidence: float = Field(default=0, ge=0, le=1)
    items: list[Item] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list)


def decimal_value(value: str) -> Decimal | None:
    value = value.strip()
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", value):
        return None
    try:
        number = Decimal(value.replace(",", ""))
        return number if number.is_finite() and number >= 0 else None
    except InvalidOperation:
        return None


class ItemEdit(StrictModel):
    code: str = Field(default="", max_length=100)
    qty: str = Field(max_length=40)
    uom: str = Field(min_length=1, max_length=20)

    @field_validator("qty")
    @classmethod
    def valid_qty(cls, value: str) -> str:
        if decimal_value(value) is None:
            raise ValueError("จำนวนต้องเป็นเลขไม่ติดลบ เช่น 1.00 หรือ 1,000.50")
        return value.strip()

    @field_validator("uom")
    @classmethod
    def valid_uom(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("กรุณาระบุหน่วย")
        return value.strip().upper()


class DocumentEdit(StrictModel):
    po: str = Field(min_length=1, max_length=100)
    items: list[ItemEdit] = Field(min_length=1, max_length=200)

    @field_validator("po")
    @classmethod
    def valid_po(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("กรุณาระบุ PO")
        return value.strip()


class ComparisonEdit(StrictModel):
    revision: int = Field(ge=1)
    checking: DocumentEdit
    invoice: DocumentEdit


class RowResult(StrictModel):
    code: str
    checking_qty: str = ""
    invoice_qty: str = ""
    checking_normalized: str | None = None
    invoice_normalized: str | None = None
    checking_uom: str = ""
    invoice_uom: str = ""
    status: Status


class Result(StrictModel):
    status: Status
    po_status: Status
    qty_status: Status
    checking_po_normalized: str
    invoice_po_normalized: str
    rows: list[RowResult]
    reasons: list[str]


class DocumentResponse(StrictModel):
    kind: Kind
    filename: str
    ocr_text: str
    evidence: list[Evidence]
    original: Extracted
    current: Extracted


class ComparisonResponse(StrictModel):
    id: str
    created_at: datetime
    updated_at: datetime
    revision: int
    reviewed: bool
    edited: bool
    result: Result
    documents: list[DocumentResponse]


class HistoryItem(StrictModel):
    id: str
    created_at: datetime
    reviewed: bool
    status: Status
    po: str


class HistoryResponse(StrictModel):
    page: int
    page_size: int
    total: int
    items: list[HistoryItem]
