import json

import pytest
from fastapi import HTTPException

from app.services.book_service import BookService, MAX_CHAPTER_CHARS, MIN_CHAPTER_WARNING_CHARS
from app.services.parser import MarkdownSplitter
from app.services.prompts import PromptId, PromptRegistry


class FakeSession:
    def __init__(self):
        self.objects = []
        self.commits = 0

    def add(self, obj):
        self.objects.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        obj.id = 123


class WarningTranslator:
    api_key = "test-key"

    def __init__(self):
        self.calls = []

    async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
        self.calls.append(
            {
                "user_prompt": user_prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
            }
        )
        return json.dumps(
            {
                "severity": "warning",
                "issues": [
                    {
                        "code": "short_chapter",
                        "message": "Chapter 1.1 looks unusually short.",
                    }
                ],
                "recommendation": "Review the split before importing.",
            }
        )


class BlockedTranslator:
    api_key = "test-key"

    async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
        return json.dumps(
            {
                "severity": "blocked",
                "issues": [{"code": "bad_split", "message": "The chapter split is not usable."}],
                "recommendation": "Fix the Markdown headings before importing.",
            }
        )


@pytest.mark.asyncio
async def test_import_preflight_hard_blocks_chapter_over_limit_without_creating_records_or_files(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    db = FakeSession()
    content = "# 1 Introduction\n" + ("x" * (MAX_CHAPTER_CHARS + 1))

    with pytest.raises(HTTPException) as exc_info:
        await BookService.create_book_from_content(
            "large.md",
            content,
            db,
            force=True,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["preflight"]["severity"] == "blocked"
    assert exc_info.value.detail["preflight"]["chapters"][0]["chapter_index"] == "1"
    assert exc_info.value.detail["preflight"]["chapters"][0]["title"] == "Introduction"
    assert exc_info.value.detail["preflight"]["chapters"][0]["char_count"] == MAX_CHAPTER_CHARS + 18
    assert db.objects == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_import_preflight_local_warning_returns_confirmation_and_force_import_proceeds(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    translator = WarningTranslator()
    monkeypatch.setattr("app.services.book_service.TranslatorService", lambda: translator)
    content = "# 1 Introduction\nBody\n\n# 1.1 Groups\nTiny"

    outline_preview = await BookService.create_book_from_content("algebra.md", content, FakeSession())

    assert outline_preview["requires_confirmation"] is True
    assert outline_preview["confirmation_type"] == "outline"
    assert outline_preview["outline"]["nodes"][0]["key"] == "1"
    assert list(tmp_path.iterdir()) == []

    selected_ids = [
        node["id"]
        for node in outline_preview["outline"]["nodes"]
        if node["key"] in {"1", "1.1"}
    ]
    preview = await BookService.create_book_from_content(
        "algebra.md",
        content,
        FakeSession(),
        outline_selection=selected_ids,
    )

    assert preview["requires_confirmation"] is True
    assert preview["confirmation_type"] == "preflight"
    assert preview["preflight"]["severity"] == "warning"
    assert preview["preflight"]["issues"][0]["code"] == "chapter_too_short"
    assert list(tmp_path.iterdir()) == []

    db = FakeSession()
    imported = await BookService.create_book_from_content(
        "algebra.md",
        content,
        db,
        force=True,
        outline_selection=selected_ids,
    )

    assert imported["book_id"] == 123
    assert imported["total_chapters"] == 2
    assert len(db.objects) == 3
    assert any(tmp_path.iterdir())
    assert len(translator.calls) == 0


@pytest.mark.asyncio
async def test_import_outline_confirmation_splits_only_selected_level_one_headings(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    content = "\n".join(
        [
            "# §28 Computation of de Rham Cohomology",
            "Body 28",
            "# 28.1 Cohomology Vector Space of a Torus",
            "Body 28.1",
            "# Problems",
            "Problem body",
            "# §29 Proof of Homotopy Invariance",
            "Body 29",
        ]
    )
    outline = MarkdownSplitter().analyze_outline(content)
    selected_ids = [node["id"] for node in outline["nodes"] if node["key"] in {"28", "29"}]

    db = FakeSession()
    imported = await BookService.create_book_from_content(
        "de-rham.md",
        content,
        db,
        outline_selection=selected_ids,
    )

    assert imported["total_chapters"] == 2
    chapters = [obj for obj in db.objects if obj.__class__.__name__ == "Chapter"]
    assert [chapter.chapter_index for chapter in chapters] == ["28", "29"]
    assert chapters[0].title_en == "Computation of de Rham Cohomology"
    first_chapter_path = next(tmp_path.rglob("28.md"))
    assert "28.1 Cohomology Vector Space" in first_chapter_path.read_text(encoding="utf-8")
    assert "# Problems" in first_chapter_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_import_preflight_llm_block_cannot_be_forced(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("IMPORT_PREFLIGHT_LLM", "1")
    monkeypatch.setattr("app.services.book_service.TranslatorService", lambda *args, **kwargs: BlockedTranslator())
    db = FakeSession()

    with pytest.raises(HTTPException) as exc_info:
        await BookService.create_book_from_content(
            "bad-split.md",
            "# 1 Introduction\nThis chapter has enough text for local checks.",
            db,
            force=True,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["preflight"]["severity"] == "blocked"
    assert db.objects == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_import_preflight_prompt_uses_chapter_table_without_full_content(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("IMPORT_PREFLIGHT_LLM", "1")
    translator = WarningTranslator()
    monkeypatch.setattr("app.services.book_service.TranslatorService", lambda *args, **kwargs: translator)
    body = "This full chapter body must not be sent to the preflight LLM. " * 2
    content = f"# 1 Introduction\n{body}\n\n# 1.1 Groups\nThis section has enough text for local checks."

    await BookService.create_book_from_content("algebra.md", content, FakeSession(), force=True)

    user_prompt = translator.calls[0]["user_prompt"]
    assert "Chapter list:" in user_prompt
    assert "1 | Introduction |" in user_prompt
    assert "1.1 | Groups |" in user_prompt
    assert "chars" in user_prompt
    assert body not in user_prompt


def test_import_preflight_local_checks_group_major_split_issues():
    chunks = [
        {"chapter_index": "3", "title": "Beliefs About P? NP 24", "content": "x" * 104},
        {"chapter_index": "4", "title": "Why Is Proving P != NP Difficult? 29", "content": "x" * 62},
        {"chapter_index": "5", "title": "Strengthenings", "content": "x" * 1523},
        {"chapter_index": "0", "title": "导入前置内容", "content": "x" * 12},
        {"chapter_index": "1", "title": "Introduction", "content": "x" * 2000},
        {"chapter_index": "3", "title": "Beliefs About P? NP", "content": "x" * 9065},
    ]

    preflight = BookService.run_import_local_preflight(chunks)

    assert preflight["severity"] == "warning"
    issue_codes = {issue["code"] for issue in preflight["issues"]}
    assert issue_codes == {"duplicate_chapter_indexes", "chapter_index_order", "chapter_too_short"}
    assert f"少于 {MIN_CHAPTER_WARNING_CHARS} 个字符" in preflight["issues"][2]["message"]
    assert preflight["issues"][0]["examples"] == ["3: Beliefs About P? NP 24 / Beliefs About P? NP"]
    assert preflight["issues"][1]["examples"] == ["5 -> 0"]


def test_import_preflight_ignores_source_line_fallbacks_when_checking_semantic_order():
    chunks = [
        {"chapter_index": "0", "title": "导入前置内容", "content": "x" * 40},
        {"chapter_index": "line-5", "title": "合情推理", "content": "x" * 500},
        {"chapter_index": "line-511", "title": "定量规则", "content": "x" * 500},
        {"chapter_index": "line-1432", "title": "初等抽样论", "content": "x" * 500},
        {"chapter_index": "line-2538", "title": "初等假设检验", "content": "x" * 500},
        {"chapter_index": "line-3339", "title": "概率论的怪异应用", "content": "x" * 500},
    ]

    preflight = BookService.run_import_local_preflight(chunks)

    assert preflight["severity"] == "ok"
    assert [chapter["chapter_index"] for chapter in preflight["chapters"]] == [
        "0",
        "line-5",
        "line-511",
        "line-1432",
        "line-2538",
        "line-3339",
    ]
    assert [chapter["position"] for chapter in preflight["chapters"]] == [1, 2, 3, 4, 5, 6]
    assert preflight["chapters"][1]["display_index"] == ""
    assert preflight["chapters"][1]["source_line"] == 5


def test_resolve_import_source_prefers_directory_full_md_when_no_meta_json(tmp_path):
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    full_md = book_dir / "full.md"
    full_md.write_text("# 1 Introduction\nBody", encoding="utf-8")

    import_type, source, meta_path = BookService.resolve_import_source(str(book_dir))

    assert import_type == "markdown"
    assert source == full_md
    assert meta_path is None


def test_resolve_import_source_prefers_preprocessed_meta_json_over_full_md(tmp_path):
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    meta_path = book_dir / "meta.json"
    meta_path.write_text("{}", encoding="utf-8")
    full_md = book_dir / "full.md"
    full_md.write_text("# 1 Introduction\nBody", encoding="utf-8")

    import_type, source, resolved_meta = BookService.resolve_import_source(str(book_dir))

    assert import_type == "preprocessed"
    assert source == book_dir
    assert resolved_meta == meta_path


def test_classify_chapter_content_type_uses_math_book_keywords_case_insensitively():
    cases = {
        "Exercises": "exercise",
        "EXERCISES 3.1": "exercise",
        "习题": "exercise",
        "Problem Set": "exercise",
        "Review Problems": "exercise",
        "Selected Exercises": "exercise",
        "Miscellaneous Problems": "exercise",
        "CHALLENGE QUESTIONS": "exercise",
        "Exercises and Solutions": "exercise",
        "Example 2.3 Gaussian Elimination": "example",
        "Worked Examples": "example",
        "例题": "example",
        "Appendix A Background": "appendix",
        "附录": "appendix",
        "References": "reference",
        "Further Reading": "reference",
        "Bibliography": "reference",
        "Symbol Index": "reference",
        "索引": "reference",
        "Preface": "preface",
        "Table of Contents": "preface",
        "目录": "preface",
        "Vector Spaces": "main_text",
    }

    for title, expected in cases.items():
        assert BookService.classify_chapter_content_type(title, "") == expected

    assert (
        BookService.classify_chapter_content_type(
            "Linear Maps",
            "This section says 例如 when introducing a concept, but it is ordinary exposition.",
        )
        == "main_text"
    )


def test_import_preflight_chapter_table_includes_rule_based_content_type():
    chunks = [
        {"chapter_index": "1", "title": "Groups", "content": "Body"},
        {"chapter_index": "1.1", "title": "EXERCISES", "content": "Problems"},
    ]

    table = BookService.build_import_preflight_chapter_table(chunks)

    assert "1 | Groups | main_text | 4 chars" in table
    assert "1.1 | EXERCISES | exercise | 8 chars" in table


def test_import_preflight_prompt_distinguishes_source_line_fallbacks_from_chapter_numbers():
    system_prompt = PromptRegistry.get(PromptId.IMPORT_PREFLIGHT).system

    assert "line-N" in system_prompt
    assert "never compare it as a semantic chapter number" in system_prompt
