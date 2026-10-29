"""Generate fictitious documents, with no customer or supplier data."""
from pathlib import Path
import pymupdf

target = Path(__file__).resolve().parents[2] / "fixtures" / "generated"
target.mkdir(parents=True, exist_ok=True)
samples = {
    "checking": ["SYNTHETIC CHECKING SHEET - DEVELOPMENT ONLY", "ASN No. 1132536", "Quantity Plan (CS) = 1", "Quantity Plan (MU) = 5"],
    "invoice": ["SYNTHETIC INVOICE - DEVELOPMENT ONLY", "PO No./SRN No.: 1132536", "QTY 1.00 CS"],
}
for name, lines in samples.items():
    with pymupdf.open() as document:
        page = document.new_page()
        for index, text in enumerate(lines):
            page.insert_text((50, 60 + index * 50), text, fontsize=16)
        document.save(target / f"{name}.pdf")
print(f"Synthetic documents created in {target}")
