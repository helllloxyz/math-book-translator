import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.base import get_db
from app.models.schema import Chapter


class FakeResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class FakeSession:
    def __init__(self, row):
        self.row = row

    async def execute(self, query):
        return FakeResult(self.row)


@pytest.mark.asyncio
async def test_get_chapter_learning_loads_context_for_chapter(monkeypatch):
    chapter = Chapter(id=7, book_id=3, chapter_index="2.1", title_en="Vector spaces", order=1)
    expected_context = {
        "summary": "Chapter summary",
        "concepts": [{"name": "Vector space", "description": "A linear structure."}],
        "key_theorems": [],
        "dependencies": ["Fields"],
    }
    calls = []

    def fake_load_learning_context(book_uuid, chapter_index):
        calls.append((book_uuid, chapter_index))
        return expected_context

    async def override_get_db():
        yield FakeSession((chapter, "book-uuid"))

    monkeypatch.setattr(
        "app.routers.chapters.LearningContextService.load_learning_context",
        fake_load_learning_context,
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get("/chapters/7/learning")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == expected_context
    assert calls == [("book-uuid", "2.1")]


@pytest.mark.asyncio
async def test_get_chapter_learning_returns_404_for_missing_chapter(monkeypatch):
    async def override_get_db():
        yield FakeSession(None)

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.get("/chapters/404/learning")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Chapter not found"}
