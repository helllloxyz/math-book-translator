from types import SimpleNamespace

import pytest

from app.main import app
from app.services.chapter_source_service import ChapterSourceService


@pytest.mark.asyncio
async def test_chapter_context_prefers_translated_body_without_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    chapter = SimpleNamespace(chapter_index="2.1", title_zh="向量空间", title_en="Vector spaces")
    raw = tmp_path / "book-uuid" / "book_md" / "2_1.md"
    translated = tmp_path / "book-uuid" / "book_trans_md" / "2_1_trans_zh.md"
    raw.parent.mkdir(parents=True)
    translated.parent.mkdir(parents=True)
    raw.write_text("source body", encoding="utf-8")
    translated.write_text("译文正文", encoding="utf-8")

    context = await ChapterSourceService.chapter_context("book-uuid", chapter)

    assert context["body"] == "译文正文"
    assert context["body_language"] == "translated"
    assert not (tmp_path / "book-uuid" / "book_learning").exists()


@pytest.mark.asyncio
async def test_chapter_context_returns_complete_body(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    chapter = SimpleNamespace(chapter_index="3", title_zh=None, title_en="Long chapter")
    body = "# Start\n\n" + ("A" * 30000) + "\n\nEND-MARKER"
    raw = tmp_path / "book-uuid" / "book_md" / "3.md"
    raw.parent.mkdir(parents=True)
    raw.write_text(body, encoding="utf-8")

    context = await ChapterSourceService.chapter_context("book-uuid", chapter)

    assert context["body"] == body
    assert context["body"].endswith("END-MARKER")


def test_learning_context_endpoint_is_removed():
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/chapters/{chapter_id}/learning" not in route_paths
