import pytest

from app.services.guide_compiler_service import GuideCompilerService
from app.services.prompts import PromptRegistry, PromptId


def test_guide_paths_use_safe_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    path = GuideCompilerService.get_guide_path("book-uuid", "../01-overview!")

    assert path == tmp_path / "book-uuid" / "book_guides" / "01-overview.md"
    assert path.parent == tmp_path / "book-uuid" / "book_guides"


def test_extract_guides_json_from_markdown_fenced_response():
    response = """
    ```json
    {
      "guides": [
        {
          "slug": "01-overview",
          "title": "导读一：全书核心问题",
          "scope_type": "book",
          "scope_id": "book",
          "markdown": "# 导读一：全书核心问题\\n内容"
        }
      ]
    }
    ```
    """

    guides = GuideCompilerService.extract_guides_json(response)

    assert guides == [
        {
            "slug": "01-overview",
            "title": "导读一：全书核心问题",
            "scope_type": "book",
            "scope_id": "book",
            "filename": "01-overview.md",
            "id": "guide:01-overview.md",
            "source_type": "book_guide",
            "source_id": "guide:book:01-overview",
            "markdown": "# 导读一：全书核心问题\n内容",
        }
    ]


def test_extract_guides_json_fallback_scans_for_first_guides_object():
    response = """
    Metadata: {"model": "example", "tokens": 123}

    {
      "guides": [
        {
          "slug": "01-overview",
          "title": "导读一",
          "markdown": "# 导读一"
        }
      ]
    }
    """

    guides = GuideCompilerService.extract_guides_json(response)

    assert guides[0]["slug"] == "01-overview"
    assert guides[0]["title"] == "导读一"
    assert guides[0]["scope_type"] == "book"


def test_build_chapter_guide_prompt_uses_only_one_chapter_context_and_output_budgets():
    prompt = GuideCompilerService.build_chapter_guide_prompt(
        book_title="Differential Forms",
        chapter_context={"chapter_index": "1", "title": "Forms", "summary": "Forms summary", "concepts": []},
    )

    assert "Differential Forms" in prompt
    assert "Forms summary" in prompt
    assert "Stokes summary" not in prompt
    assert "chapter-level guides" in prompt
    assert f"At most {GuideCompilerService.MAX_CHAPTER_GUIDES_PER_CHAPTER} chapter guide" in prompt
    assert f"markdown at most {GuideCompilerService.MAX_GUIDE_MARKDOWN_CHARS} characters" in prompt
    assert f"Mermaid diagrams at most {GuideCompilerService.MAX_MERMAID_NODES} nodes" in prompt


def test_build_book_guide_prompt_uses_chapter_guide_summaries_not_learning_contexts():
    prompt = GuideCompilerService.build_book_guide_prompt(
        book_title="Differential Forms",
        chapter_guide_inputs=[
            {
                "child_index": "1",
                "child_title": "Forms",
                "slug": "chapter-map",
                "title": "Forms guide",
                "summary": "Chapter guide summary only.",
            }
        ],
    )

    assert "Differential Forms" in prompt
    assert "Chapter guide summary only." in prompt
    assert "top_level_child_guide_inputs" in prompt
    assert "learning contexts" not in prompt.lower()
    assert f"At most {GuideCompilerService.MAX_BOOK_GUIDES} book guide" in prompt
    assert f"markdown at most {GuideCompilerService.MAX_GUIDE_MARKDOWN_CHARS} characters" in prompt


def test_build_directory_guide_prompt_uses_direct_child_guide_summaries():
    prompt = GuideCompilerService.build_directory_guide_prompt(
        book_title="Differential Forms",
        directory_context={"directory_index": "1.1", "title": "Forms"},
        child_guide_inputs=[
            {
                "child_index": "1.1.1",
                "child_title": "Tangent spaces",
                "summary": "Tangent spaces child summary.",
            }
        ],
    )

    assert "directory-level guides" in prompt
    assert "Differential Forms" in prompt
    assert '"directory_index": "1.1"' in prompt
    assert "Tangent spaces child summary." in prompt
    assert "direct_child_guide_inputs" in prompt
    assert f"At most {GuideCompilerService.MAX_DIRECTORY_GUIDES_PER_DIRECTORY} directory guide" in prompt


@pytest.mark.asyncio
async def test_write_guides_persists_markdown_files(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    guides = [
        {
            "slug": "01-overview",
            "title": "导读一：全书核心问题",
            "scope_type": "book",
            "scope_id": "book",
            "markdown": "# 导读一：全书核心问题\n内容",
        },
        {
            "slug": "concept-map",
            "title": "导读二：概念地图",
            "scope_type": "chapter",
            "scope_id": "1",
            "markdown": "# 导读二：概念地图\n```mermaid\ngraph TD\nA-->B\n```",
        },
    ]

    written = await GuideCompilerService.write_guides("book-uuid", guides)

    assert written[0]["source_type"] == "book_guide"
    assert written[0]["source_id"] == "guide:book:01-overview"
    assert written[1]["source_type"] == "chapter_guide"
    assert written[1]["source_id"] == "guide:chapter:1:concept-map"
    assert (tmp_path / "book-uuid" / "book_guides" / "01-overview.md").read_text(encoding="utf-8") == guides[0]["markdown"]
    assert (tmp_path / "book-uuid" / "book_guides" / "chapter-1-concept-map.md").read_text(encoding="utf-8") == guides[1]["markdown"]
    manifest = (tmp_path / "book-uuid" / "book_guides" / "guides.json").read_text(encoding="utf-8")
    assert "chapter-1-concept-map.md" in manifest


@pytest.mark.asyncio
async def test_generate_top_down_guides_rolls_up_directory_nodes_bottom_up(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    learning_dir = tmp_path / "book-uuid" / "book_learning"
    learning_dir.mkdir(parents=True)
    for stem, summary in {
        "1_1_1": "Leaf 1.1.1 summary.",
        "1_1_2": "Leaf 1.1.2 summary.",
        "1_2": "Leaf 1.2 summary.",
    }.items():
        (learning_dir / f"{stem}.md").write_text(
            "\n".join(
                [
                    "# Chapter Learning Context",
                    "",
                    "## Summary",
                    summary,
                    "",
                    "## Concepts",
                    "- None",
                    "",
                    "## Key Theorems",
                    "- None",
                    "",
                    "## Dependencies",
                    "- None",
                ]
            ),
            encoding="utf-8",
        )

    class Book:
        uuid = "book-uuid"
        title = "Hierarchical Book"

    class Chapter:
        def __init__(self, chapter_index, title_en, order):
            self.chapter_index = chapter_index
            self.title_en = title_en
            self.title_zh = None
            self.order = order

    class HierarchyTranslator:
        def __init__(self):
            self.prompts = []

        async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
            self.prompts.append(user_prompt)
            if "chapter-level guides" in user_prompt and '"chapter_index": "1.1.1"' in user_prompt:
                return """
                {"guides": [{"slug": "map", "title": "Guide 1.1.1", "summary": "Summary guide 1.1.1.", "markdown": "# 1.1.1"}]}
                """
            if "chapter-level guides" in user_prompt and '"chapter_index": "1.1.2"' in user_prompt:
                return """
                {"guides": [{"slug": "map", "title": "Guide 1.1.2", "summary": "Summary guide 1.1.2.", "markdown": "# 1.1.2"}]}
                """
            if "chapter-level guides" in user_prompt and '"chapter_index": "1.2"' in user_prompt:
                return """
                {"guides": [{"slug": "map", "title": "Guide 1.2", "summary": "Summary guide 1.2.", "markdown": "# 1.2"}]}
                """
            if "directory-level guides" in user_prompt and '"directory_index": "1.1"' in user_prompt:
                assert "Summary guide 1.1.1." in user_prompt
                assert "Summary guide 1.1.2." in user_prompt
                assert "Summary guide 1.2." not in user_prompt
                return """
                {"guides": [{"slug": "overview", "title": "Guide 1.1", "summary": "Summary guide 1.1.", "markdown": "# 1.1"}]}
                """
            if "directory-level guides" in user_prompt and '"directory_index": "1"' in user_prompt:
                assert "Summary guide 1.1." in user_prompt
                assert "Summary guide 1.2." in user_prompt
                assert "Summary guide 1.1.1." not in user_prompt
                return """
                {"guides": [{"slug": "overview", "title": "Guide 1", "summary": "Summary guide 1.", "markdown": "# 1"}]}
                """
            assert "book-level guides" in user_prompt
            assert "Summary guide 1." in user_prompt
            assert "Summary guide 1.1." not in user_prompt
            assert "Summary guide 1.2." not in user_prompt
            return """
            {"guides": [{"slug": "book", "title": "Book Guide", "summary": "Book summary.", "markdown": "# Book"}]}
            """

    translator = HierarchyTranslator()
    guides = await GuideCompilerService.generate_top_down_guides(
        Book(),
        [
            Chapter("1", "Chapter 1", 1),
            Chapter("1.1", "Section 1.1", 2),
            Chapter("1.1.1", "Leaf 1.1.1", 3),
            Chapter("1.1.2", "Leaf 1.1.2", 4),
            Chapter("1.2", "Leaf 1.2", 5),
        ],
        translator,
    )

    assert len(translator.prompts) == 6
    assert [guide["filename"] for guide in guides] == [
        "chapter-1_1_1-map.md",
        "chapter-1_1_2-map.md",
        "directory-1_1-overview.md",
        "chapter-1_2-map.md",
        "directory-1-overview.md",
        "book.md",
    ]
    assert [guide["scope_type"] for guide in guides] == [
        "chapter",
        "chapter",
        "directory",
        "chapter",
        "directory",
        "book",
    ]


@pytest.mark.asyncio
async def test_generate_top_down_guides_stages_chapter_then_book_prompts(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    learning_dir = tmp_path / "book-uuid" / "book_learning"
    learning_dir.mkdir(parents=True)
    (learning_dir / "1.md").write_text(
        "\n".join(
            [
                "# Chapter Learning Context",
                "",
                "## Summary",
                "Forms are alternating multilinear tools for integration.",
                "",
                "## Concepts",
                "- **Differential form**: A coordinate-free integrand.",
                "",
                "## Key Theorems",
                "- **Stokes theorem**: Boundary integral equals derivative integral.",
                "",
                "## Dependencies",
                "- Linear algebra",
            ]
        ),
        encoding="utf-8",
    )
    (learning_dir / "2.md").write_text(
        "\n".join(
            [
                "# Chapter Learning Context",
                "",
                "## Summary",
                "Integration uses forms on oriented manifolds.",
                "",
                "## Concepts",
                "- **Orientation**: A consistent sign convention.",
                "",
                "## Key Theorems",
                "- None",
                "",
                "## Dependencies",
                "- Differential forms",
            ]
        ),
        encoding="utf-8",
    )

    class Book:
        uuid = "book-uuid"
        title = "Differential Forms"

    class Chapter:
        def __init__(self, chapter_index, title_zh=None, title_en=None):
            self.chapter_index = chapter_index
            self.title_zh = title_zh
            self.title_en = title_en

    class StubTranslator:
        client_type = "openai"
        prompts = []

        async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
            self.prompts.append(user_prompt)
            assert "Differential Forms" in user_prompt
            assert system_prompt == PromptRegistry.get(PromptId.TOP_DOWN_GUIDE).system
            assert temperature == 0.3
            if "chapter-level guides" in user_prompt and '"chapter_index": "1"' in user_prompt:
                assert "Forms are alternating multilinear tools for integration." in user_prompt
                assert "Integration uses forms on oriented manifolds." not in user_prompt
                return """
                {
                  "guides": [
                    {
                      "slug": "chapter-map",
                      "title": "第一章导读",
                      "summary": "Forms chapter guide summary.",
                      "scope_type": "chapter",
                      "scope_id": "1",
                      "markdown": "# 第一章导读\\n内容"
                    }
                  ]
                }
                """
            if "chapter-level guides" in user_prompt and '"chapter_index": "2"' in user_prompt:
                assert "Integration uses forms on oriented manifolds." in user_prompt
                assert "Forms are alternating multilinear tools for integration." not in user_prompt
                return """
                {
                  "guides": [
                    {
                      "slug": "chapter-map",
                      "title": "第二章导读",
                      "summary": "Integration chapter guide summary.",
                      "scope_type": "chapter",
                      "scope_id": "2",
                      "markdown": "# 第二章导读\\n内容"
                    }
                  ]
                }
                """
            assert "book-level guides" in user_prompt
            assert "Forms chapter guide summary." in user_prompt
            assert "Integration chapter guide summary." in user_prompt
            assert "Forms are alternating multilinear tools for integration." not in user_prompt
            assert "Integration uses forms on oriented manifolds." not in user_prompt
            return """
            {
              "guides": [
                {
                  "slug": "01-overview",
                  "title": "导读一：全书核心问题",
                  "scope_type": "book",
                  "scope_id": "book",
                  "markdown": "# 导读一：全书核心问题\\n内容"
                }
              ]
            }
            """

    translator = StubTranslator()
    guides = await GuideCompilerService.generate_top_down_guides(
        book=Book(),
        chapters=[
            Chapter("1", title_zh="微分形式", title_en="Forms"),
            Chapter("2", title_zh="积分", title_en="Integration"),
        ],
        translator=translator,
    )

    assert len(translator.prompts) == 3
    assert [guide["filename"] for guide in guides] == [
        "chapter-1-chapter-map.md",
        "chapter-2-chapter-map.md",
        "01-overview.md",
    ]


@pytest.mark.asyncio
async def test_generate_top_down_guides_forces_expected_scope_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    learning_dir = tmp_path / "book-uuid" / "book_learning"
    learning_dir.mkdir(parents=True)
    (learning_dir / "1.md").write_text(
        "\n".join(
            [
                "# Chapter Learning Context",
                "",
                "## Summary",
                "Chapter summary.",
                "",
                "## Concepts",
                "- **Concept**: Detail.",
                "",
                "## Key Theorems",
                "- None",
                "",
                "## Dependencies",
                "- None",
            ]
        ),
        encoding="utf-8",
    )

    class Book:
        uuid = "book-uuid"
        title = "Scoped Guides"

    class Chapter:
        chapter_index = "1"
        title_zh = None
        title_en = "Chapter One"

    class WrongScopeTranslator:
        async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
            if "chapter-level guides" in user_prompt:
                return """
                {
                  "guides": [
                    {
                      "slug": "map",
                      "title": "Wrongly Scoped Chapter Guide",
                      "scope_type": "book",
                      "scope_id": "book",
                      "markdown": "# Chapter guide"
                    }
                  ]
                }
                """
            return """
            {
              "guides": [
                {
                  "slug": "overview",
                  "title": "Wrongly Scoped Book Guide",
                  "scope_type": "chapter",
                  "scope_id": "1",
                  "markdown": "# Book guide"
                }
              ]
            }
            """

    guides = await GuideCompilerService.generate_top_down_guides(Book(), [Chapter()], WrongScopeTranslator())

    chapter_guide = next(guide for guide in guides if guide["title"] == "Wrongly Scoped Chapter Guide")
    book_guide = next(guide for guide in guides if guide["title"] == "Wrongly Scoped Book Guide")

    assert chapter_guide["scope_type"] == "chapter"
    assert chapter_guide["scope_id"] == "1"
    assert chapter_guide["filename"] == "chapter-1-map.md"
    assert chapter_guide["source_id"] == "guide:chapter:1:map"
    assert book_guide["scope_type"] == "book"
    assert book_guide["scope_id"] == "book"
    assert book_guide["filename"] == "overview.md"
    assert book_guide["source_id"] == "guide:book:overview"
