import threading
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import ocr
from .comparison import compare
from .config import settings
from .db import Comparison, Document, Revision, get_db
from .extraction import extract
from .files import prepared_uploads, render_pages
from .schemas import ComparisonEdit, ComparisonResponse, Extracted, HistoryResponse, Item

app = FastAPI(title="PDA Document Check", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins,
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])
processing = threading.BoundedSemaphore(1)


def serialize(record: Comparison):
    return {"id": record.id, "created_at": record.created_at, "updated_at": record.updated_at,
            "revision": record.revision, "reviewed": record.reviewed, "edited": record.edited, "result": record.result,
            "documents": [{"kind": d.kind, "filename": d.filename, "ocr_text": d.ocr_text,
                           "evidence": d.evidence, "original": d.original, "current": d.current}
                          for d in record.documents]}


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "ocr": "lazy-loaded"}


@app.post("/api/comparisons", status_code=201, response_model=ComparisonResponse)
def create_comparison(checking: UploadFile = File(...), invoice: UploadFile = File(...),
                      db: Session = Depends(get_db)):
    if not processing.acquire(blocking=False):
        raise HTTPException(429, "ระบบกำลังอ่านเอกสารอื่น กรุณาลองใหม่ ภาพของคุณยังอยู่")
    try:
        record = Comparison(id=str(uuid4()))
        extracted = {}
        with prepared_uploads(checking, invoice) as paths:
            for kind, upload, path in zip(("checking", "invoice"), (checking, invoice), paths):
                pages = render_pages(path)
                try:
                    lines = ocr.engine.read(pages)
                    barcode = None
                    if kind == "checking":
                        cell_reader = getattr(ocr.engine, "split_checking_cells", None)
                        if callable(cell_reader):
                            lines = cell_reader(pages[0], lines)
                        barcode_reader = getattr(ocr.engine, "read_checking_barcode", None)
                        barcode = barcode_reader(pages[0], lines) if callable(barcode_reader) else None
                        if barcode is not None:
                            lines.append(barcode)
                    data = extract(lines, kind, checking_barcode=barcode)
                    if kind == "checking" and (not data.items or all(item.uom != "CS" for item in data.items)
                                                  or any("ค่าจากตำแหน่งคอลัมน์" in warning for warning in data.warnings)):
                        targeted_reader = getattr(ocr.engine, "read_quantity_plan_cs", None)
                        targeted_value = targeted_reader(pages[0], lines) if callable(targeted_reader) else None
                        if targeted_value is not None:
                            lines.append(targeted_value)
                            data = extract(lines, kind, checking_cs_value=targeted_value, checking_barcode=barcode)
                except Exception:
                    # Never expose document content, filesystem paths or engine internals.
                    raise HTTPException(503, "OCR ยังไม่พร้อม กรุณาลองใหม่ หรือตรวจการดาวน์โหลดโมเดลที่เซิร์ฟเวอร์") from None
                finally:
                    for page in pages:
                        page.close()
                extracted[kind] = data
                record.documents.append(Document(id=str(uuid4()), kind=kind,
                    filename=(upload.filename or "document").replace("\\", "/").split("/")[-1][:255],
                    ocr_text="\n".join(line.text for line in lines), evidence=[line.model_dump() for line in lines],
                    original=data.model_dump(), current=data.model_dump()))
        record.result = compare(extracted["checking"], extracted["invoice"], settings().min_confidence).model_dump()
        db.add(record)
        db.commit()
        db.refresh(record)
        return serialize(record)
    finally:
        checking.file.close()
        invoice.file.close()
        processing.release()


@app.get("/api/comparisons", response_model=HistoryResponse)
def history(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    records = db.scalars(select(Comparison).order_by(Comparison.created_at.desc(), Comparison.id)
                         .offset((page - 1) * page_size).limit(page_size)).all()
    return {"page": page, "page_size": page_size, "total": db.scalar(select(func.count()).select_from(Comparison)),
            "items": [{"id": r.id, "created_at": r.created_at, "reviewed": r.reviewed,
                       "status": r.result["status"], "po": r.result["checking_po_normalized"]} for r in records]}


def find_record(db: Session, id: UUID, lock: bool = False):
    query = select(Comparison).where(Comparison.id == str(id))
    if lock:
        query = query.with_for_update()
    record = db.scalar(query)
    if record is None:
        raise HTTPException(404, "ไม่พบประวัติรายการนี้")
    return record


@app.get("/api/comparisons/{id}", response_model=ComparisonResponse)
def detail(id: UUID, db: Session = Depends(get_db)):
    return serialize(find_record(db, id))


@app.patch("/api/comparisons/{id}", response_model=ComparisonResponse)
def update_comparison(id: UUID, payload: ComparisonEdit, db: Session = Depends(get_db)):
    record = find_record(db, id, lock=True)
    if record.revision != payload.revision:
        raise HTTPException(409, "รายการถูกแก้ไขจากหน้าจออื่นแล้ว กรุณาเปิดประวัติใหม่ก่อนแก้ไข")
    values = {}
    for document in record.documents:
        edit = getattr(payload, document.kind)
        original = Extracted.model_validate(document.original)
        po_changed = edit.po.strip() != original.po.strip()
        original_items = original.items
        current_items = []
        for index, item in enumerate(edit.items):
            prior = original_items[index] if index < len(original_items) else None
            changed = prior is None or (item.code, item.qty, item.uom) != (prior.code, prior.qty, prior.uom)
            current_items.append(Item(**item.model_dump(),
                source="แก้โดยผู้ใช้" if changed else prior.source,
                confidence=1.0 if changed else prior.confidence))
        current = Extracted(po=edit.po, po_source="แก้โดยผู้ใช้" if po_changed else original.po_source,
                            po_confidence=1.0 if po_changed else original.po_confidence, items=current_items,
                            warnings=original.warnings)
        document.current = current.model_dump()
        values[document.kind] = current
    # Saving a changed field does not mean the user attested to every source line.
    record.reviewed = False
    record.edited = any(
        document.current["po"] != document.original["po"] or
        [{key: item[key] for key in ("code", "qty", "uom")} for item in document.current["items"]] !=
        [{key: item[key] for key in ("code", "qty", "uom")} for item in document.original["items"]]
        for document in record.documents
    )
    record.revision += 1
    record.result = compare(values["checking"], values["invoice"], settings().min_confidence, reviewed=False).model_dump()
    db.add(Revision(id=str(uuid4()), comparison_id=record.id, revision=record.revision,
                    values={k: v.model_dump() for k, v in values.items()}, result=record.result))
    db.commit()
    db.refresh(record)
    return serialize(record)
