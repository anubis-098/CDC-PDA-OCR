import io
import os
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, Revision, get_db
from app.main import app
from app.schemas import Evidence
from app import ocr


@pytest.fixture
def client(tmp_path, monkeypatch):
    database = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(database)
    sessions = sessionmaker(database)

    def dependency():
        with sessions() as session:
            yield session

    class FakeEngine:
        def read(self, pages):
            return [Evidence(text=text, confidence=.99, page=1) for text in
                    ("PO No. 1132536", "Quantity Plan (CS) = 1", "QTY 1.00 CS")]

    monkeypatch.setattr(settings(), "upload_dir", tmp_path)
    monkeypatch.setattr(ocr, "engine", FakeEngine())
    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as test_client:
        yield test_client, sessions, tmp_path
    app.dependency_overrides.clear()
    database.dispose()


def image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def uploads(content=None):
    content = image_bytes() if content is None else content
    return {"checking": ("../../checking.png", content, "image/png"), "invoice": ("invoice.png", content, "image/png")}


def test_roundtrip_audit_and_concurrent_edit(client):
    api, sessions, directory = client
    created = api.post("/api/comparisons", files=uploads())
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["result"]["status"] == "match"
    assert data["documents"][0]["filename"] == "checking.png"
    assert not list(directory.iterdir())
    assert api.get("/api/comparisons").json()["total"] == 1
    assert api.get(f'/api/comparisons/{data["id"]}').status_code == 200
    edit = {"po": "1132536", "items": [{"code": "", "qty": "2", "uom": "CS"}]}
    body = {"revision": 1, "checking": edit, "invoice": {**edit, "items": [{"code": "", "qty": "1.00", "uom": "CS"}]}}
    updated = api.patch(f'/api/comparisons/{data["id"]}', json=body)
    assert updated.status_code == 200, updated.text
    assert updated.json()["result"]["status"] == "mismatch"
    assert updated.json()["documents"][0]["original"]["items"][0]["qty"] == "1"
    assert updated.json()["revision"] == 2
    assert updated.json()["edited"] is True
    assert api.patch(f'/api/comparisons/{data["id"]}', json=body).status_code == 409
    with sessions() as session:
        assert len(session.scalars(select(Revision)).all()) == 1


def test_invalid_files_and_cleanup(client):
    api, _, directory = client
    assert api.post("/api/comparisons", files=uploads(b"not an image")).status_code == 415
    assert api.post("/api/comparisons", files=uploads(b"")).status_code == 422
    assert not list(directory.iterdir())
    assert api.get(f"/api/comparisons/{uuid4()}").status_code == 404
    assert api.get("/api/comparisons?page=0").status_code == 422


def test_file_limit_and_engine_failure(client, monkeypatch):
    api, _, directory = client
    monkeypatch.setattr(settings(), "max_file_bytes", 4)
    assert api.post("/api/comparisons", files=uploads()).status_code == 413
    assert not list(directory.iterdir())
    monkeypatch.setattr(settings(), "max_file_bytes", 10 * 1024 * 1024)

    def fail(_):
        raise RuntimeError("private document text")

    monkeypatch.setattr(ocr.engine, "read", fail)
    response = api.post("/api/comparisons", files=uploads())
    assert response.status_code == 503
    assert "private document" not in response.text
    assert not list(directory.iterdir())


def test_invalid_quantities_rejected(client):
    api, _, _ = client
    data = api.post("/api/comparisons", files=uploads()).json()
    for qty in ("NaN", "Infinity", "-2", "1,00"):
        edit = {"po": "1132536", "items": [{"qty": qty, "uom": "CS"}]}
        assert api.patch(f'/api/comparisons/{data["id"]}', json={"revision": 1, "checking": edit, "invoice": edit}).status_code == 422
