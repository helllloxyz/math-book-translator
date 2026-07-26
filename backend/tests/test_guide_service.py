import pytest

from app.services.book_storage import BookStorage
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
