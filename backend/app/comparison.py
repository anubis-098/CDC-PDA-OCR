import re

from .schemas import Extracted, Item, Result, RowResult, Status, decimal_value


def normalize_po(value: str) -> str:
    # Preserve leading zeroes; only formatting separators are ignored.
    return re.sub(r"[\s\-]+", "", value).upper()


def normalize_code(value: str) -> str:
    return value.strip().upper()


def compare(checking: Extracted, invoice: Extracted, threshold: float = 0.85,
            reviewed: bool = False) -> Result:
    a, b = normalize_po(checking.po), normalize_po(invoice.po)
    reasons: list[str] = []
    po_status: Status = "match" if a and a == b else "mismatch"
    if not a or not b or (not reviewed and min(checking.po_confidence, invoice.po_confidence) < threshold):
        po_status = "review"
        reasons.append("ไม่พบ PO หรือความเชื่อมั่นต่ำ กรุณาตรวจเลขอ้างอิง")
    pairs: list[tuple[Item, Item]] = []
    left, right = checking.items, invoice.items
    ambiguous = False
    if len(left) == len(right) == 1:
        if left[0].code and right[0].code and normalize_code(left[0].code) != normalize_code(right[0].code):
            ambiguous = True
        else:
            pairs = [(left[0], right[0])]
    elif left and right:
        lc = [normalize_code(i.code) for i in left]
        rc = [normalize_code(i.code) for i in right]
        if "" in lc or "" in rc or len(set(lc)) != len(lc) or len(set(rc)) != len(rc) or set(lc) != set(rc):
            ambiguous = True
        else:
            lookup = dict(zip(rc, right))
            pairs = [(item, lookup[normalize_code(item.code)]) for item in left]
    else:
        ambiguous = True
    rows: list[RowResult] = []
    for x, y in pairs:
        qx, qy = decimal_value(x.qty), decimal_value(y.qty)
        ux, uy = x.uom.strip().upper(), y.uom.strip().upper()
        state: Status
        if qx is None or qy is None or not ux or not uy or (not reviewed and min(x.confidence, y.confidence) < threshold):
            state = "review"
        elif ux != uy:
            state = "unit_mismatch"
        else:
            state = "match" if qx == qy else "mismatch"
        rows.append(RowResult(code=x.code or y.code or "รายการเดียว", checking_qty=x.qty,
                              invoice_qty=y.qty, checking_normalized=str(qx) if qx is not None else None,
                              invoice_normalized=str(qy) if qy is not None else None,
                              checking_uom=ux, invoice_uom=uy, status=state))
    states = {r.status for r in rows}
    if ambiguous or not rows or "review" in states or (not reviewed and (checking.warnings or invoice.warnings)):
        qty_status: Status = "review"
        reasons.append("ข้อมูลรายการไม่ครบหรือกำกวม กรุณาตรวจรายการ รหัส จำนวน และหน่วยทั้งหมด")
    elif "unit_mismatch" in states:
        qty_status = "unit_mismatch"
        reasons.append("หน่วยต่างกัน ระบบไม่แปลงหน่วยหรือรวมยอดให้อัตโนมัติ")
    elif "mismatch" in states:
        qty_status = "mismatch"
    else:
        qty_status = "match"
    status: Status = "match"
    for candidate in ("review", "unit_mismatch", "mismatch"):
        if candidate in (po_status, qty_status):
            status = candidate
            break
    return Result(status=status, po_status=po_status, qty_status=qty_status,
                  checking_po_normalized=a, invoice_po_normalized=b, rows=rows, reasons=reasons)
