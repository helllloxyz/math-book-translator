import json
import re
from pathlib import Path
from typing import Sequence

from fastapi import HTTPException

from app.services.book_storage import BookStorage
from app.services.llm_json import extract_json_candidate
from app.services.translator import TranslatorService


class LatexRepairService:
    SMART_QUOTE_TRANSLATION = str.maketrans(
        {
            "\u201c": '"',
            "\u201d": '"',
            "\u2018": "'",
            "\u2019": "'",
        }
    )

    @staticmethod
    def normalize_content_target(content_target: str | None) -> str:
        value = str(content_target or "translated").strip().lower()
        if value in {"raw", "source"}:
            return "raw"
        if value in {"translated", "target"}:
            return "translated"
        raise HTTPException(status_code=400, detail="content_target must be raw or translated")

    @staticmethod
    def content_path(book_uuid: str, chapter_index: str, content_target: str | None) -> Path:
        normalized = LatexRepairService.normalize_content_target(content_target)
        raw_path = BookStorage.raw_chapter_path(book_uuid, chapter_index)
        if normalized == "raw":
            return raw_path

        translated_path = BookStorage.translated_chapter_path(book_uuid, chapter_index)
        return translated_path if translated_path.exists() else raw_path

    @staticmethod
    def build_repair_prompt(selected_text: str, failed_candidates: Sequence[str] | None = None) -> str:
        failed = [candidate for candidate in failed_candidates or [] if str(candidate).strip()]
        parts = [
            "Repair this selected Markdown/LaTeX fragment so it renders correctly in KaTeX.",
            "Return JSON only with this shape: {\"replacement\": \"...\"}.",
            "Keep surrounding prose unchanged when possible.",
            "Use standard Markdown math delimiters: $...$, $$...$$, \\(...\\), or \\[...\\].",
            "Do not explain the fix.",
            "",
            "Selected fragment:",
            selected_text,
        ]
        if failed:
            parts.extend(
                [
                    "",
                    "Previous candidates that the user said failed to render correctly:",
                    json.dumps(failed, ensure_ascii=False, indent=2),
                    "Do not return the same failed candidate again.",
                ]
            )
        return "\n".join(parts)

    @staticmethod
    def _strip_json_math_wrapper(text: str) -> str:
        stripped = text.strip()
        if (
            stripped.startswith("\\(")
            and stripped.endswith("\\)")
            and "replacement" in stripped.translate(LatexRepairService.SMART_QUOTE_TRANSLATION)
        ):
            return stripped[2:-2].strip()
        return stripped

    @staticmethod
    def _extract_replacement_from_jsonish_text(text: str) -> tuple[bool, str | None]:
        variants = [
            text,
            text.translate(LatexRepairService.SMART_QUOTE_TRANSLATION),
            LatexRepairService._strip_json_math_wrapper(text.translate(LatexRepairService.SMART_QUOTE_TRANSLATION)),
        ]
        for variant in variants:
            try:
                parsed = extract_json_candidate(variant, validator=lambda value: isinstance(value, dict))
            except ValueError:
                parsed = None
            if parsed is not None:
                replacement = str(parsed.get("replacement") or "").strip()
                return True, replacement or None

            match = re.search(
                r'"replacement"\s*:\s*"(?P<replacement>.*?)"\s*\}?\s*$',
                variant,
                re.DOTALL,
            )
            if match:
                replacement = match.group("replacement").strip()
                return True, replacement or None

        return False, None

    @staticmethod
    def normalize_replacement_text(replacement_text: str) -> str:
        replacement = str(replacement_text or "").strip()
        for _ in range(3):
            found_jsonish, nested = LatexRepairService._extract_replacement_from_jsonish_text(replacement)
            if found_jsonish and not nested:
                return ""
            if not nested or nested == replacement:
                break
            replacement = nested.strip()
        return replacement

    @staticmethod
    async def suggest_repair(
        selected_text: str,
        failed_candidates: Sequence[str] | None = None,
        translator: TranslatorService | None = None,
    ) -> str:
        selected = str(selected_text or "").strip()
        if not selected:
            raise HTTPException(status_code=400, detail="selected_text is required")

        service = translator or TranslatorService(task="chat")
        system_prompt = (
            "You repair malformed LaTeX in Markdown math content for a math reader. "
            "Return strict JSON only. Preserve mathematical meaning and prose."
        )
        raw_response = await service.complete(
            LatexRepairService.build_repair_prompt(selected, failed_candidates),
            system_prompt,
            temperature=0.1,
        )
        replacement = LatexRepairService.normalize_replacement_text(raw_response)
        if not replacement:
            raise HTTPException(status_code=502, detail="LLM response did not include a replacement")
        return replacement

    @staticmethod
    def apply_exact_replacement(
        book_uuid: str,
        chapter_index: str,
        content_target: str | None,
        original_text: str,
        replacement_text: str,
    ) -> str:
        original = str(original_text or "")
        replacement = LatexRepairService.normalize_replacement_text(replacement_text)
        if not original.strip():
            raise HTTPException(status_code=400, detail="original_text is required")
        if not replacement.strip():
            raise HTTPException(status_code=400, detail="replacement_text is required")

        path = LatexRepairService.content_path(book_uuid, chapter_index, content_target)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Chapter content file not found")

        content = path.read_text(encoding="utf-8")
        matches = content.count(original)
        if matches != 1:
            raise HTTPException(
                status_code=409,
                detail=f"Replacement requires exactly one unique match, found {matches}.",
            )

        updated = content.replace(original, replacement, 1)
        path.write_text(updated, encoding="utf-8")
        return updated
