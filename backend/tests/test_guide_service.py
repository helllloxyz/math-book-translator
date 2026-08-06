import pytest

from app.services.book_storage import BookStorage
from app.services.guide_compiler_service import GuideCompilerService
from app.services.guide_service import GuideService


@pytest.mark.asyncio
async def test_read_guide_uses_exact_filename_without_slug_aliasing(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    guide_dir = tmp_path / "book-uuid" / "book_guides"
    guide_dir.mkdir(parents=True)
    (guide_dir / "study guide!.md").write_text("# Exact guide\nBody", encoding="utf-8")

    guide = await GuideService.read_guide("book-uuid", "study guide!.md")

    assert guide == {"content": "# Exact guide\nBody"}


@pytest.mark.asyncio
async def test_read_guide_rejects_missing_exact_filename_even_if_sanitized_neighbor_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    guide_dir = tmp_path / "book-uuid" / "book_guides"
    guide_dir.mkdir(parents=True)
    (guide_dir / "guide.md").write_text("# Neighbor", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        await GuideService.read_guide("book-uuid", "guide!.md")


@pytest.mark.asyncio
async def test_list_guides_reads_manifest_scope_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    guide_dir = tmp_path / "book-uuid" / "book_guides"
    guide_dir.mkdir(parents=True)
    (guide_dir / "overview.md").write_text("# Overview\nBody", encoding="utf-8")
    BookStorage.guide_manifest_path("book-uuid").write_text(
        """
        [
          {
            "id": "guide:overview.md",
            "filename": "overview.md",
            "title": "Overview",
            "scope_type": "chapter",
            "scope_id": "1",
            "source_type": "chapter_guide",
            "source_id": "guide:chapter:1:overview"
          }
        ]
        """,
        encoding="utf-8",
    )

    guides = await GuideService.list_guides("book-uuid")

    assert guides == [
        {
            "id": "guide:overview.md",
            "filename": "overview.md",
            "title": "Overview",
            "scope_type": "chapter",
            "scope_id": "1",
            "source_type": "chapter_guide",
            "source_id": "guide:chapter:1:overview",
            "source_title": "Overview",
        }
    ]


@pytest.mark.asyncio
async def test_generate_chapter_guide_writes_only_the_requested_chapter(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    translated = tmp_path / "book-uuid" / "book_trans_md" / "2_trans_zh.md"
    translated.parent.mkdir(parents=True)
    translated.write_text("本章译文。", encoding="utf-8")

    class Book:
        uuid = "book-uuid"
        title = "Test Book"

    class Chapter:
        chapter_index = "2"
        title_zh = "第二章"
        title_en = "Chapter Two"

    class Translator:
        async def complete(self, user_prompt, system_prompt, temperature=0.3):
            return '''{"guides": [{"slug": "preview", "title": "读前 60 秒", "markdown": "# 读前 60 秒"}]}'''

    guides = await GuideCompilerService.generate_chapter_guide(Book(), Chapter(), Translator())

    assert [guide["scope_type"] for guide in guides] == ["chapter"]
    assert [guide["scope_id"] for guide in guides] == ["2"]
    assert (tmp_path / "book-uuid" / "book_guides" / "chapter-2-preview.md").exists()
