import json
import zipfile
import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.services.book_service import BookService
from app.services.translator import LLMConfigurationError


class FakeSession:
    def __init__(self, existing_book=None):
        self.objects = []
        self.existing_book = existing_book

    def add(self, obj):
        self.objects.append(obj)

    async def execute(self, _query):
        class FakeResult:
            def __init__(self, existing_book):
                self.existing_book = existing_book

            def scalar_one_or_none(self):
                return self.existing_book

        return FakeResult(self.existing_book)

    async def commit(self):
        pass

    async def refresh(self, obj):
        obj.id = 123


def make_package_upload(files: dict[str, str], filename: str = "book.zip") -> UploadFile:
    package = BytesIO()
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as package_zip:
        for name, content in files.items():
            package_zip.writestr(name, content)
    package.seek(0)
    return UploadFile(filename=filename, file=package)


@pytest.mark.asyncio
async def test_import_preprocessed_book_creates_guide_and_user_dirs(tmp_path):
    source_dir = tmp_path / "preprocessed-book"
    source_dir.mkdir()
    meta_path = source_dir / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "title": "Imported Book",
                "original_filename": "imported.md",
                "chapters": [
                    {"chapter_index": "1.1", "title_en": "Intro", "order": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    await BookService.import_preprocessed_book(str(source_dir), str(meta_path), FakeSession())

    assert not (source_dir / "book_learning").exists()
    assert (source_dir / "book_guides").is_dir()
    assert (source_dir / "book_user").is_dir()


@pytest.mark.asyncio
async def test_create_book_from_content_persists_chapter_content_type_and_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    db = FakeSession()
    content = "# 1 Vector Spaces\nBody\n\n# 1.1 Exercises\nProblems"

    await BookService.create_book_from_content(
        "linear-algebra.md",
        content,
        db,
        force=True,
        preflight=False,
    )

    chapters = [obj for obj in db.objects if obj.__class__.__name__ == "Chapter"]
    assert [chapter.content_type for chapter in chapters] == ["main_text", "exercise"]

    meta_path = next(tmp_path.iterdir()) / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert [chapter["content_type"] for chapter in meta["chapters"]] == ["main_text", "exercise"]


@pytest.mark.asyncio
async def test_build_book_package_includes_book_storage_files(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    book = FakeBook(uuid="book-uuid")
    book.id = 7
    book.title = "Linear Algebra"
    book_dir = tmp_path / book.uuid
    for relative_path in (
        "meta.json",
        "book_md/1.md",
        "book_trans_md/1_trans_zh.md",
        "book_learning/legacy.md",
        "book_guides/guides.json",
    ):
        path = book_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative_path, encoding="utf-8")

    package_buffer, filename = await BookService.build_book_package(7, FakeSession(existing_book=book))

    assert filename == "Linear Algebra-book-uuid.zip"
    with zipfile.ZipFile(package_buffer) as package_zip:
        names = set(package_zip.namelist())
    assert {
        "book-uuid/meta.json",
        "book-uuid/book_md/1.md",
        "book-uuid/book_trans_md/1_trans_zh.md",
        "book-uuid/book_guides/guides.json",
    }.issubset(names)
    assert "book-uuid/book_learning/legacy.md" not in names


@pytest.mark.asyncio
async def test_build_book_package_syncs_current_title_to_meta_json(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    book = FakeBook(uuid="book-uuid")
    book.id = 7
    book.title = "Renamed Book"
    book_dir = tmp_path / book.uuid
    book_dir.mkdir()
    (book_dir / "meta.json").write_text(
        json.dumps(
            {
                "uuid": book.uuid,
                "title": "Original Book",
                "original_filename": "original.md",
                "chapters": [{"chapter_index": "1", "title_en": "Intro", "order": 0}],
            }
        ),
        encoding="utf-8",
    )

    package_buffer, _filename = await BookService.build_book_package(7, FakeSession(existing_book=book))

    with zipfile.ZipFile(package_buffer) as package_zip:
        exported_meta = json.loads(package_zip.read("book-uuid/meta.json").decode("utf-8"))
    disk_meta = json.loads((book_dir / "meta.json").read_text(encoding="utf-8"))
    assert exported_meta["title"] == "Renamed Book"
    assert disk_meta["title"] == "Renamed Book"


@pytest.mark.asyncio
async def test_import_book_package_creates_book_and_counts_existing_translation(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    meta = {
        "uuid": "package-uuid",
        "title": "Packaged Book",
        "original_filename": "packaged.md",
        "chapters": [{"chapter_index": "1", "title_en": "Intro", "order": 0}],
    }
    upload = make_package_upload(
        {
            "package-uuid/meta.json": json.dumps(meta),
            "package-uuid/book_md/1.md": "source",
            "package-uuid/book_trans_md/1_trans_zh.md": "translated",
            "package-uuid/book_learning/1.md": "learning",
            "package-uuid/book_guides/guides.json": "[]",
        }
    )
    db = FakeSession()

    result = await BookService.import_book_package(upload, db)

    assert result["book_id"] == 123
    assert result["total_chapters"] == 1
    assert (tmp_path / "package-uuid" / "book_guides" / "guides.json").exists()
    book = next(obj for obj in db.objects if obj.__class__.__name__ == "Book")
    assert book.translation_total == 1
    assert book.translation_completed == 1
    assert book.status.value == "translated"


@pytest.mark.asyncio
async def test_import_book_package_rejects_duplicate_uuid_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    existing_dir = tmp_path / "package-uuid"
    existing_dir.mkdir()
    (existing_dir / "marker.txt").write_text("keep", encoding="utf-8")
    existing_book = FakeBook(uuid="package-uuid")
    meta = {
        "uuid": "package-uuid",
        "title": "Packaged Book",
        "chapters": [{"chapter_index": "1", "title_en": "Intro", "order": 0}],
    }
    upload = make_package_upload(
        {
            "package-uuid/meta.json": json.dumps(meta),
            "package-uuid/book_md/1.md": "source",
        }
    )

    with pytest.raises(HTTPException) as exc:
        await BookService.import_book_package(upload, FakeSession(existing_book=existing_book))

    assert exc.value.status_code == 409
    assert (existing_dir / "marker.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.asyncio
async def test_import_book_package_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    upload = make_package_upload({"../x": "escape"})

    with pytest.raises(HTTPException) as exc:
        await BookService.import_book_package(upload, FakeSession())

    assert exc.value.status_code == 400
    assert not (tmp_path.parent / "x").exists()


@pytest.mark.asyncio
async def test_import_book_package_requires_valid_meta_json(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    upload = make_package_upload({"package-uuid/book_md/1.md": "source"})

    with pytest.raises(HTTPException) as exc:
        await BookService.import_book_package(upload, FakeSession())

    assert exc.value.status_code == 400
    assert "meta.json" in str(exc.value.detail)


def test_get_chapter_filenames_preserves_legacy_non_dot_characters(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    raw_path, trans_path = BookService.get_chapter_filenames("book-uuid", "Appendix A-1")

    assert raw_path == str(tmp_path / "book-uuid" / "book_md" / "Appendix A-1.md")
    assert trans_path == str(tmp_path / "book-uuid" / "book_trans_md" / "Appendix A-1_trans_zh.md")


def test_translation_concurrency_defaults_to_five(monkeypatch):
    monkeypatch.delenv("TRANSLATION_CONCURRENCY", raising=False)

    assert BookService.get_translation_concurrency() == 5

class FakeChapter:
    def __init__(self, chapter_index, title_en="Chapter"):
        self.chapter_index = chapter_index
        self.title_en = title_en
        self.title_zh = None


class FakeBook:
    def __init__(self, uuid="book-uuid"):
        self.uuid = uuid


class SlowTranslator:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.calls = []

    async def translate_text(self, text):
        import asyncio

        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.calls.append(text)
        await asyncio.sleep(0.02)
        self.active -= 1
        return f"ZH:{text}"


class FailingTranslator(SlowTranslator):
    async def translate_text(self, text):
        self.calls.append(text)
        raise RuntimeError("provider down")


class MissingConfigTranslator(SlowTranslator):
    async def translate_text(self, text):
        self.calls.append(text)
        raise LLMConfigurationError("Configure an LLM provider and model in Settings before starting translation.")


@pytest.mark.asyncio
async def test_guide_generation_does_not_pregenerate_quizzes(monkeypatch):
    calls = []

    async def generate_guides(book, chapters, translator):
        calls.append("guides")

    monkeypatch.setattr(
        "app.services.book_service.GuideCompilerService.generate_top_down_guides",
        generate_guides,
    )

    book = FakeBook()
    book.status = None
    await BookService.generate_guides_for_translated_book(
        book,
        [FakeChapter("1")],
        SlowTranslator(),
        FakeSession(),
        1,
    )

    assert calls == ["guides"]


@pytest.mark.asyncio
async def test_guide_generation_failure_is_not_hidden(monkeypatch):
    async def fail_guides(book, chapters, translator):
        raise RuntimeError("guide provider failed")

    monkeypatch.setattr(
        "app.services.book_service.GuideCompilerService.generate_top_down_guides",
        fail_guides,
    )
    book = FakeBook()
    book.status = None

    with pytest.raises(RuntimeError, match="guide provider failed"):
        await BookService.generate_guides_for_translated_book(
            book,
            [FakeChapter("1")],
            SlowTranslator(),
            FakeSession(),
            1,
        )

    assert book.status.value == "generating_guides"


@pytest.mark.asyncio
async def test_translation_plan_counts_existing_files_and_skips_them(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    book = FakeBook()
    chapters = [FakeChapter("1"), FakeChapter("2")]

    raw_1 = tmp_path / book.uuid / "book_md" / "1.md"
    raw_2 = tmp_path / book.uuid / "book_md" / "2.md"
    trans_1 = tmp_path / book.uuid / "book_trans_md" / "1_trans_zh.md"
    raw_1.parent.mkdir(parents=True)
    trans_1.parent.mkdir(parents=True)
    raw_1.write_text("one", encoding="utf-8")
    raw_2.write_text("two", encoding="utf-8")
    trans_1.write_text("translated", encoding="utf-8")

    plan = await BookService.build_translation_plan(book, chapters)

    assert plan.total == 2
    assert plan.completed == 1
    assert [chapter.chapter_index for chapter in plan.pending] == ["2"]


def test_require_translation_configuration_rejects_missing_llm_before_work_starts(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.services.settings_service.SettingsService.get_current_settings",
        staticmethod(lambda: {"storage_path": str(tmp_path), "llm_profiles": {}}),
    )
    monkeypatch.setattr(
        "app.services.llm_credentials.FileCredentialRegistry.list",
        lambda _self: [],
    )

    book = FakeBook()
    chapter = FakeChapter("1")
    raw_path = tmp_path / book.uuid / "book_md" / "1.md"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("source text", encoding="utf-8")

    with pytest.raises(LLMConfigurationError, match="Configure an LLM provider"):
        asyncio.run(BookService.require_translation_configuration(book, [chapter]))


@pytest.mark.asyncio
async def test_translate_pending_chapters_runs_concurrently_and_skips_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    book = FakeBook()
    chapters = [FakeChapter("1"), FakeChapter("2"), FakeChapter("3")]
    for chapter in chapters:
        path = tmp_path / book.uuid / "book_md" / f"{chapter.chapter_index}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(chapter.chapter_index, encoding="utf-8")

    existing = tmp_path / book.uuid / "book_trans_md" / "1_trans_zh.md"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("already translated", encoding="utf-8")

    translator = SlowTranslator()
    progress = []

    result = await BookService.translate_pending_chapters(
        book,
        chapters,
        translator,
        concurrency=2,
        on_progress=lambda completed, total, failed: progress.append((completed, total, failed)),
    )

    assert result.total == 3
    assert result.completed == 3
    assert result.failed == 0
    assert translator.max_active == 2
    assert translator.calls == ["2", "3"]
    assert (tmp_path / book.uuid / "book_trans_md" / "2_trans_zh.md").read_text(encoding="utf-8") == "ZH:2"
    assert not (tmp_path / book.uuid / "book_learning").exists()
    assert progress[-1] == (3, 3, 0)


@pytest.mark.asyncio
async def test_translate_pending_chapters_marks_provider_errors_failed_without_writing_source(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    book = FakeBook()
    chapter = FakeChapter("1")
    raw_path = tmp_path / book.uuid / "book_md" / "1.md"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("source text", encoding="utf-8")

    result = await BookService.translate_pending_chapters(
        book,
        [chapter],
        FailingTranslator(),
        concurrency=1,
    )

    assert result.total == 1
    assert result.completed == 0
    assert result.failed == 1
    trans_path = tmp_path / book.uuid / "book_trans_md" / "1_trans_zh.md"
    assert not trans_path.exists()


@pytest.mark.asyncio
async def test_translate_pending_chapters_does_not_retry_missing_llm_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    book = FakeBook()
    chapter = FakeChapter("1")
    raw_path = tmp_path / book.uuid / "book_md" / "1.md"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("source text", encoding="utf-8")
    translator = MissingConfigTranslator()

    result = await BookService.translate_pending_chapters(
        book,
        [chapter],
        translator,
        concurrency=1,
    )

    assert result.total == 1
    assert result.completed == 0
    assert result.failed == 1
    assert translator.calls == ["source text"]
