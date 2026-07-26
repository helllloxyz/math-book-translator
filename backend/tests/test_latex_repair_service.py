import pytest
from fastapi import HTTPException

from app.services.book_storage import BookStorage
from app.services.latex_repair_service import LatexRepairService


class FakeTranslator:
    def __init__(self, response='{"replacement": "\\\\[x^2\\\\]"}'):
        self.response = response
        self.calls = []

    async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
        self.calls.append(
            {
                "user_prompt": user_prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
            }
        )
        return self.response


def test_apply_exact_replacement_updates_only_unique_match(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    path = BookStorage.translated_chapter_path("book-uuid", "1")
    path.parent.mkdir(parents=True)
    path.write_text("Before\n\\[x2\\]\nAfter", encoding="utf-8")

    updated = LatexRepairService.apply_exact_replacement(
        book_uuid="book-uuid",
        chapter_index="1",
        content_target="translated",
        original_text="\\[x2\\]",
        replacement_text="\\[x^2\\]",
    )

    assert updated == "Before\n\\[x^2\\]\nAfter"
    assert path.read_text(encoding="utf-8") == updated


def test_apply_exact_replacement_rejects_ambiguous_matches(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    path = BookStorage.raw_chapter_path("book-uuid", "1")
    path.parent.mkdir(parents=True)
    path.write_text("$x2$ and $x2$", encoding="utf-8")

    with pytest.raises(HTTPException) as exc:
        LatexRepairService.apply_exact_replacement(
            book_uuid="book-uuid",
            chapter_index="1",
            content_target="raw",
            original_text="$x2$",
            replacement_text="$x^2$",
        )

    assert exc.value.status_code == 409
    assert "unique" in exc.value.detail
    assert path.read_text(encoding="utf-8") == "$x2$ and $x2$"


@pytest.mark.asyncio
async def test_suggest_repair_tells_llm_failed_candidates():
    translator = FakeTranslator()

    replacement = await LatexRepairService.suggest_repair(
        selected_text="\\[x2\\]",
        failed_candidates=["\\[x^2"],
        translator=translator,
    )

    assert replacement == "\\[x^2\\]"
    assert "failed" in translator.calls[0]["user_prompt"].lower()
    assert "\\[x^2" in translator.calls[0]["user_prompt"]


@pytest.mark.asyncio
async def test_suggest_repair_unwraps_jsonish_replacement_rendered_as_math():
    translator = FakeTranslator(
        '\\({“replacement”: “$\\operatorname{sgn}(\\sigma) = (-1)^{\\text{\\# inversions in } \\sigma}$”}\\)'
    )

    replacement = await LatexRepairService.suggest_repair(
        selected_text="broken",
        translator=translator,
    )

    assert replacement == "$\\operatorname{sgn}(\\sigma) = (-1)^{\\text{\\# inversions in } \\sigma}$"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ['{"replacement": ""}', '{"foo": "bar"}'])
async def test_suggest_repair_rejects_json_without_replacement(response):
    translator = FakeTranslator(response)

    with pytest.raises(HTTPException) as exc:
        await LatexRepairService.suggest_repair(
            selected_text="broken",
            translator=translator,
        )

    assert exc.value.status_code == 502
    assert "replacement" in exc.value.detail


def test_apply_exact_replacement_unwraps_jsonish_replacement_text(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    path = BookStorage.translated_chapter_path("book-uuid", "1")
    path.parent.mkdir(parents=True)
    path.write_text("Before\nbroken\nAfter", encoding="utf-8")

    updated = LatexRepairService.apply_exact_replacement(
        book_uuid="book-uuid",
        chapter_index="1",
        content_target="translated",
        original_text="broken",
        replacement_text='{"replacement": "$x^2$"}',
    )

    assert updated == "Before\n$x^2$\nAfter"
    assert path.read_text(encoding="utf-8") == updated
