from pathlib import Path
import os
import time

import pytest
from fastapi import HTTPException
from PIL import Image
import pymupdf

from app.cleanup import cleanup
from app.files import render_pages


def test_pdf_page_limit_and_password(tmp_path):
    path = tmp_path / "document.pdf"
    with pymupdf.open() as document:
        for _ in range(6):
            document.new_page()
        document.save(path)
    with pytest.raises(HTTPException) as error:
        render_pages(path)
    assert error.value.status_code == 422
    secure = tmp_path / "secure.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(secure, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="reader")
    with pytest.raises(HTTPException):
        render_pages(secure)


def test_pdf_rendering_and_exif_orientation(tmp_path):
    path = tmp_path / "document.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 60), "Synthetic PO 1132536")
        document.save(path)
    pages = render_pages(path)
    assert len(pages) == 1 and pages[0].mode == "RGB"
    for page in pages:
        page.close()
    path = tmp_path / "rotated.jpg"
    source = Image.new("RGB", (40, 20))
    exif = source.getexif()
    exif[274] = 6
    source.save(path, exif=exif)
    pages = render_pages(path)
    assert pages[0].size == (20, 40)
    pages[0].close()


def test_cleanup_only_old_owned_directories(tmp_path: Path):
    now = time.time()
    old = tmp_path / "request-old"
    recent = tmp_path / "request-new"
    unrelated = tmp_path / "keep-this"
    for path in (old, recent, unrelated):
        path.mkdir()
    os.utime(old, (now - 90000, now - 90000))
    os.utime(unrelated, (now - 90000, now - 90000))
    assert cleanup(tmp_path, now) == 1
    assert recent.exists() and unrelated.exists() and not old.exists()
