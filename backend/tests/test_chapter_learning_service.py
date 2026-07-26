import pytest

from app.services.learning_context_service import LearningContextService
from app.services.prompts import PromptRegistry, PromptId


def test_learning_paths_use_safe_chapter_index(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    path = LearningContextService.get_learning_path("book-uuid", "2.1")

    assert path == tmp_path / "book-uuid" / "book_learning" / "2_1.md"


def test_learning_paths_reject_traversal_like_indices(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    path = LearningContextService.get_learning_path("book-uuid", "../Vector/Spaces")

    assert path == tmp_path / "book-uuid" / "book_learning" / "Vector_Spaces.md"
    assert path.parent == tmp_path / "book-uuid" / "book_learning"
    assert path.name == "Vector_Spaces.md"


def test_default_learning_context_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    context = LearningContextService.load_learning_context("book-uuid", "2.1")

    assert context["summary"] == ""
    assert context["concepts"] == []
    assert context["key_theorems"] == []
    assert context["dependencies"] == []


def test_format_chat_context_excludes_chapter_content():
    context = {
        "summary": "This chapter explains orientations and Stokes theorem.",
        "concepts": [
            {"name": "Orientation", "description": "A consistent choice of volume sign."}
        ],
        "key_theorems": [
            {"name": "Stokes theorem", "statement": "Boundary integrals equal exterior derivative integrals."}
        ],
        "dependencies": ["Manifolds", "Differential forms"],
    }

    formatted = LearningContextService.format_chat_context(
        chapter_title="Integration on Manifolds",
        learning_context=context,
    )

    assert "Integration on Manifolds" in formatted
    assert "This chapter explains orientations" in formatted
    assert "Orientation" in formatted
    assert "FULL_CHAPTER_BODY" not in formatted


def test_extract_learning_json_from_markdown_fenced_response():
    response = """
    Here is the result:

    ```json
    {
      "summary": "The chapter introduces smooth manifolds.",
      "concepts": [{"name": "Chart", "description": "A coordinate representation."}],
      "key_theorems": [],
      "dependencies": ["Topology"]
    }
    ```
    """

    parsed = LearningContextService.extract_learning_json(response)

    assert parsed["summary"] == "The chapter introduces smooth manifolds."
    assert parsed["concepts"][0]["name"] == "Chart"


def test_extract_learning_json_prefers_later_json_fence_over_earlier_braces():
    response = """
    I considered this non-result example first:
    {"summary": "Draft summary that should not be used"}

    ```json
    {
      "summary": "Use the final fenced learning context.",
      "concepts": [{"name": "Atlas", "description": "Compatible charts."}],
      "key_theorems": [],
      "dependencies": ["Charts"]
    }
    ```
    """

    parsed = LearningContextService.extract_learning_json(response)

    assert parsed["summary"] == "Use the final fenced learning context."
    assert parsed["concepts"][0]["name"] == "Atlas"


def test_extract_learning_json_fallback_scans_for_first_learning_object():
    response = """
    Metadata object before the actual answer:
    {"model": "example", "tokens": 123}

    Final object:
    {
      "summary": "Scanned valid learning context.",
      "concepts": [{"name": "Tangent space", "description": "Linearized local directions."}],
      "key_theorems": [],
      "dependencies": ["Vector spaces"]
    }
    """

    parsed = LearningContextService.extract_learning_json(response)

    assert parsed["summary"] == "Scanned valid learning context."
    assert parsed["concepts"][0]["name"] == "Tangent space"


def test_build_compile_prompt_uses_raw_text_without_translated_duplicate():
    prompt = LearningContextService.build_compile_prompt(
        chapter_title="Smooth Manifolds",
        raw_text="RAW TEXT",
        translated_text="TRANSLATED TEXT",
    )

    assert "Smooth Manifolds" in prompt
    assert "RAW TEXT" in prompt
    assert "TRANSLATED TEXT" not in prompt
    assert "Translated text" not in prompt
    assert "## Summary" in prompt
    assert "## Concepts" in prompt
    assert "$...$" in prompt
    assert "$$...$$" in prompt


def test_build_compile_prompt_uses_full_raw_text_without_translated_duplicate():
    raw_text = (
        "RAW_BEGIN\n"
        + ("raw middle notation\n" * 5000)
        + "RAW_MIDDLE_SENTINEL\n"
        + ("raw later notation\n" * 5000)
        + "RAW_END"
    )

    prompt = LearningContextService.build_compile_prompt(
        chapter_title="Long Chapter",
        raw_text=raw_text,
        translated_text="TRANSLATED TEXT",
    )

    assert raw_text in prompt
    assert "RAW_BEGIN" in prompt
    assert "RAW_END" in prompt
    assert "RAW_MIDDLE_SENTINEL" in prompt
    assert "TRANSLATED TEXT" not in prompt
    assert "[... omitted for prompt length ...]" not in prompt


def test_build_compile_prompt_declares_output_budget_rules():
    prompt = LearningContextService.build_compile_prompt(
        chapter_title="Budgeted Chapter",
        raw_text="RAW TEXT",
        translated_text="TRANSLATED TEXT",
    )

    assert f"Summary: at most {LearningContextService.SUMMARY_SENTENCE_LIMIT} sentences" in prompt
    assert f"Concepts: at most {LearningContextService.MAX_CONCEPTS}" in prompt
    assert f"Key theorems: at most {LearningContextService.MAX_KEY_THEOREMS}" in prompt
    assert f"Dependencies: at most {LearningContextService.MAX_DEPENDENCIES}" in prompt
    assert "Do not include the full chapter body" in prompt
    assert "Return Markdown only" in prompt
    assert "## Summary" in prompt
    assert "## Concepts" in prompt
    assert "## Key Theorems" in prompt
    assert "## Dependencies" in prompt


@pytest.mark.asyncio
async def test_save_learning_context_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    context = {
        "summary": "流形上的积分",
        "concepts": [
            {"name": "Orientation", "description": "A consistent choice of volume sign."}
        ],
        "key_theorems": [
            {"name": "Stokes theorem", "statement": "Boundary integrals equal exterior derivative integrals."}
        ],
        "dependencies": ["Manifolds", "Differential forms"],
    }

    saved = await LearningContextService.save_learning_context("book-uuid", "2.3", context)

    path = tmp_path / "book-uuid" / "book_learning" / "2_3.md"
    assert path.exists()
    assert path.parent.exists()
    assert saved["summary"] == "流形上的积分"
    assert saved["concepts"] == context["concepts"]
    assert saved["key_theorems"] == context["key_theorems"]
    assert saved["dependencies"] == context["dependencies"]

    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("# Chapter Learning Context")
    assert "流形上的积分" in raw
    assert "## Concepts" in raw
    assert "Orientation" in raw
    assert "## Key Theorems" in raw
    assert "Stokes theorem" in raw
    assert "## Dependencies" in raw

    loaded = LearningContextService.load_learning_context("book-uuid", "2.3")
    assert loaded == saved


@pytest.mark.asyncio
async def test_compile_chapter_learning_uses_translator_complete(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    class StubTranslator:
        client_type = "openai"

        async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
            assert "Smooth Manifolds" in user_prompt
            assert system_prompt == PromptRegistry.get(PromptId.LEARNING_CONTEXT).system
            assert temperature == 0.3
            return """
            # Chapter Learning Context

            ## Summary
            Compiled summary

            ## Concepts
            - **Atlas**: Compatible charts.

            ## Key Theorems
            - None

            ## Dependencies
            - Topology
            """

    saved = await LearningContextService.compile_chapter_learning(
        book_uuid="book-uuid",
        chapter_index="2.1",
        chapter_title="Smooth Manifolds",
        raw_text="RAW TEXT",
        translated_text="TRANSLATED TEXT",
        translator=StubTranslator(),
    )

    assert saved["summary"] == "Compiled summary"
    assert saved["concepts"][0]["name"] == "Atlas"


@pytest.mark.asyncio
async def test_compile_chapter_learning_retries_invalid_markdown_response(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.learning_context_service.asyncio.sleep", no_sleep)

    class FlakyTranslator:
        def __init__(self):
            self.calls = 0

        async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
            self.calls += 1
            if self.calls == 1:
                return "This has no expected learning context sections."
            assert "previous response could not be parsed" in user_prompt
            return """
            # Chapter Learning Context

            ## Summary
            Retried summary

            ## Concepts
            - **Atlas**: Compatible charts.

            ## Key Theorems
            - None

            ## Dependencies
            - Topology
            """

    translator = FlakyTranslator()
    saved = await LearningContextService.compile_chapter_learning(
        book_uuid="book-uuid",
        chapter_index="2.1",
        chapter_title="Smooth Manifolds",
        raw_text="RAW TEXT",
        translated_text="TRANSLATED TEXT",
        translator=translator,
    )

    assert translator.calls == 2
    assert saved["summary"] == "Retried summary"
