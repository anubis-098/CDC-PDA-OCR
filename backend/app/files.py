from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import warnings

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import settings


@contextmanager
def prepared_uploads(checking: UploadFile, invoice: UploadFile):
    cfg = settings()
    cfg.upload_dir.mkdir(parents=True, exist_ok=True)
    # Names are generated here; user filenames are metadata only.
    with TemporaryDirectory(prefix="request-", dir=cfg.upload_dir) as directory:
        paths = []
        for index, upload in enumerate((checking, invoice)):
            path = Path(directory) / f"document-{index}"
            size = 0
            with path.open("wb") as target:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > cfg.max_file_bytes:
                        raise HTTPException(413, "แต่ละไฟล์ต้องมีขนาดไม่เกิน 10 MB")
                    target.write(chunk)
            if size == 0:
                raise HTTPException(422, "ไฟล์ว่าง กรุณาเลือกไฟล์ใหม่")
            paths.append(path)
        yield paths


def render_pages(path: Path) -> list[Image.Image]:
    cfg = settings()
    with path.open("rb") as stream:
        magic = stream.read(8)
    pages: list[Image.Image] = []
    try:
        if magic.startswith(b"%PDF-"):
            import pymupdf
            with pymupdf.open(path) as document:
                if document.is_encrypted:
                    raise HTTPException(422, "ไม่รองรับ PDF ที่มีรหัสผ่าน")
                if not 1 <= len(document) <= cfg.max_pages:
                    raise HTTPException(422, "PDF ต้องมี 1–5 หน้า")
                for page in document:
                    rect = page.rect
                    if rect.width <= 0 or rect.height <= 0:
                        raise HTTPException(422, "ขนาดหน้า PDF ไม่ถูกต้อง")
                    scale = min(2.5, 2400 / max(rect.width, rect.height))
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
                    pages.append(Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples))
        elif magic.startswith(b"\xff\xd8\xff") or magic.startswith(b"\x89PNG\r\n\x1a\n"):
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as source:
                    if source.width * source.height > cfg.max_pixels:
                        raise HTTPException(422, "ภาพต้องมีขนาดไม่เกิน 25 ล้านพิกเซล")
                    if getattr(source, "n_frames", 1) != 1:
                        raise HTTPException(422, "ไม่รองรับภาพเคลื่อนไหว")
                    page = ImageOps.exif_transpose(source).convert("RGB")
                    page.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                    pages.append(page)
        else:
            raise HTTPException(415, "รองรับเฉพาะ JPG, JPEG, PNG และ PDF")
    except HTTPException:
        for page in pages:
            page.close()
        raise
    except (UnidentifiedImageError, OSError, ValueError, RuntimeError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        for page in pages:
            page.close()
        raise HTTPException(422, "อ่านไฟล์ไม่ได้ ไฟล์อาจเสียหายหรือมีขนาดภาพใหญ่เกินไป") from None
    return pages
