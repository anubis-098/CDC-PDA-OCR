"""Live OCR/API smoke test; creates one clearly synthetic history record."""
import os
import httpx
import pymupdf


def pdf(lines):
    with pymupdf.open() as document:
        page = document.new_page()
        for index, line in enumerate(lines):
            page.insert_text((50, 60 + index * 50), line, fontsize=16)
        return document.tobytes()


base = os.environ.get("SMOKE_API_URL", "http://api:8000")
with httpx.Client(base_url=base, timeout=600) as client:
    response = client.post("/api/comparisons", files={
        "checking": ("synthetic-checking.pdf", pdf([
            "SYNTHETIC CHECKING SHEET", "ASN No. 1132536",
            "Quantity Plan (CS) = 1", "Quantity Plan (MU) = 5",
        ]), "application/pdf"),
        "invoice": ("synthetic-invoice.pdf", pdf([
            "SYNTHETIC INVOICE", "PO No./SRN No.: 1132536", "QTY 1.00 CS",
        ]), "application/pdf"),
    })
    response.raise_for_status()
    data = response.json()
    print({"id": data["id"], "result": data["result"], "extracted": {
        document["kind"]: document["current"] for document in data["documents"]
    }}, flush=True)
    assert data["result"]["status"] == "match", "Live OCR requires review; inspect extraction"
    detail = client.get(f'/api/comparisons/{data["id"]}')
    detail.raise_for_status()
    assert detail.json()["id"] == data["id"]
    print("Live OCR and persisted detail passed", flush=True)
