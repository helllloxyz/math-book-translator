import json
import asyncio
import logging
from pathlib import Path
from typing import Any

from app.services.book_storage import BookStorage
from app.services.llm_json import extract_json_candidate, parse_json_text
from app.services.prompts import PromptId, PromptRegistry

logger = logging.getLogger("app.learning_context_service")


class LearningContextService:
    SUMMARY_SENTENCE_LIMIT = 4
    MAX_CONCEPTS = 12
    MAX_KEY_THEOREMS = 8
    MAX_DEPENDENCIES = 10
    COMPILE_MAX_RETRIES = 3
    _SECTION_TITLES = {
        "summary": "Summary",
        "concepts": "Concepts",
        "key_theorems": "Key Theorems",
        "dependencies": "Dependencies",
    }

    @staticmethod
    def sanitize_chapter_title(chapter_title: str) -> str:
        return BookStorage.sanitize_learning_title(chapter_title)

    @staticmethod
    def get_book_dir(book_uuid: str) -> Path:
        return BookStorage.book_dir(book_uuid)

    @staticmethod
    def get_learning_path(book_uuid: str, chapter_index: str) -> Path:
        return BookStorage.learning_path(book_uuid, chapter_index)

    @staticmethod
    def default_learning_context() -> dict[str, Any]:
        return {
            "summary": "",
            "concepts": [],
            "key_theorems": [],
            "dependencies": [],
        }

    @staticmethod
    def normalize_learning_context(data: dict[str, Any] | None) -> dict[str, Any]:
        normalized = LearningContextService.default_learning_context()
        if not isinstance(data, dict):
            return normalized

        normalized["summary"] = str(data.get("summary") or "")
        normalized["concepts"] = data.get("concepts") if isinstance(data.get("concepts"), list) else []
        normalized["key_theorems"] = data.get("key_theorems") if isinstance(data.get("key_theorems"), list) else []
        normalized["dependencies"] = data.get("dependencies") if isinstance(data.get("dependencies"), list) else []
        return normalized

    @staticmethod
    def is_learning_context_empty(data: dict[str, Any]) -> bool:
        context = LearningContextService.normalize_learning_context(data)
        return not (
            context["summary"].strip()
            or context["concepts"]
            or context["key_theorems"]
            or context["dependencies"]
        )

    @staticmethod
    def is_learning_context_candidate(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        expected_keys = {"summary", "concepts", "key_theorems", "dependencies"}
        return expected_keys.issubset(data.keys())

    @staticmethod
    def parse_learning_context_candidate(text: str) -> dict[str, Any] | None:
        parsed = parse_json_text(text)
        if not LearningContextService.is_learning_context_candidate(parsed):
            return None
        return LearningContextService.normalize_learning_context(parsed)

    @staticmethod
    def extract_learning_json(text: str) -> dict[str, Any]:
        return extract_json_candidate(
            text,
            LearningContextService.is_learning_context_candidate,
            transform=LearningContextService.normalize_learning_context,
        )

    @staticmethod
    def _escape_markdown_inline(value: Any) -> str:
        return str(value or "").replace("\n", " ").strip()

    @staticmethod
    def _format_named_items(items: list[Any], detail_key: str) -> list[str]:
        lines = []
        for item in items:
            if isinstance(item, dict):
                name = LearningContextService._escape_markdown_inline(item.get("name"))
                detail = LearningContextService._escape_markdown_inline(item.get(detail_key))
                if name and detail:
                    lines.append(f"- **{name}**: {detail}")
                elif name:
                    lines.append(f"- **{name}**")
                elif detail:
                    lines.append(f"- {detail}")
            elif item:
                lines.append(f"- {LearningContextService._escape_markdown_inline(item)}")
        return lines or ["- None"]

    @staticmethod
    def learning_context_to_markdown(context: dict[str, Any]) -> str:
        normalized = LearningContextService.normalize_learning_context(context)
        dependency_lines = [
            f"- {LearningContextService._escape_markdown_inline(dependency)}"
            for dependency in normalized["dependencies"]
            if dependency
        ] or ["- None"]
        parts = [
            "# Chapter Learning Context",
            "",
            "## Summary",
            normalized["summary"] or "None",
            "",
            "## Concepts",
            *LearningContextService._format_named_items(normalized["concepts"], "description"),
            "",
            "## Key Theorems",
            *LearningContextService._format_named_items(normalized["key_theorems"], "statement"),
            "",
            "## Dependencies",
            *dependency_lines,
            "",
        ]
        return "\n".join(parts)

    @staticmethod
    def _markdown_sections(markdown: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current: str | None = None
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                current = line[3:].strip().lower()
                sections[current] = []
                continue
            if current:
                sections[current].append(raw_line.rstrip())
        return sections

    @staticmethod
    def _parse_markdown_named_item(line: str, detail_key: str) -> dict[str, str] | str | None:
        item = line.strip()
        if not item.startswith("- "):
            return None
        item = item[2:].strip()
        if not item or item.lower() == "none":
            return None
        if item.startswith("**") and "**:" in item:
            name, detail = item[2:].split("**:", 1)
            return {"name": name.strip(), detail_key: detail.strip()}
        if item.startswith("**") and item.endswith("**"):
            return {"name": item[2:-2].strip(), detail_key: ""}
        return item

    @staticmethod
    def markdown_to_learning_context(markdown: str) -> dict[str, Any]:
        sections = LearningContextService._markdown_sections(markdown)
        summary_lines = [
            line.strip()
            for line in sections.get(LearningContextService._SECTION_TITLES["summary"].lower(), [])
            if line.strip() and line.strip().lower() != "none"
        ]
        concepts = [
            parsed
            for line in sections.get(LearningContextService._SECTION_TITLES["concepts"].lower(), [])
            if (parsed := LearningContextService._parse_markdown_named_item(line, "description"))
        ]
        key_theorems = [
            parsed
            for line in sections.get(LearningContextService._SECTION_TITLES["key_theorems"].lower(), [])
            if (parsed := LearningContextService._parse_markdown_named_item(line, "statement"))
        ]
        dependencies = []
        for line in sections.get(LearningContextService._SECTION_TITLES["dependencies"].lower(), []):
            item = line.strip()
            if item.startswith("- "):
                dependency = item[2:].strip()
                if dependency and dependency.lower() != "none":
                    dependencies.append(dependency)

        return LearningContextService.normalize_learning_context(
            {
                "summary": "\n".join(summary_lines),
                "concepts": concepts,
                "key_theorems": key_theorems,
                "dependencies": dependencies,
            }
        )

    @staticmethod
    def excerpt_prompt_text(text: str, max_chars: int) -> str:
        stripped = text.strip()
        if len(stripped) <= max_chars:
            return stripped

        head_chars = max_chars // 2
        tail_chars = max_chars - head_chars
        return (
            stripped[:head_chars].rstrip()
            + "\n\n[... omitted for prompt length ...]\n\n"
            + stripped[-tail_chars:].lstrip()
        )

    @staticmethod
    def build_compile_prompt(chapter_title: str, raw_text: str, translated_text: str) -> str:
        return f"""
You are compiling an English mathematics book chapter into reusable Chinese learning context.

Return Markdown only, using exactly these headings and bullet formats:

# Chapter Learning Context

## Summary
A concise Chinese chapter summary focused on the mathematical purpose and main logical flow.

## Concepts
- **Concept name**: Chinese explanation of meaning, intuition, and role in this chapter

## Key Theorems
- **Theorem or proposition name**: Chinese statement and role in the chapter

## Dependencies
- Prerequisite concept or earlier result

Rules:
- Do not translate the chapter line by line.
- Do not include the full chapter body.
- Do not wrap the result in a Markdown code fence.
- Preserve mathematical notation exactly where needed.
- Use LaTeX math delimiters for every formula: `$...$` for inline formulas and `$$...$$` for display formulas.
- Focus on concepts, relationships, and reusable context for chat and quiz.
- Output budget:
  - Summary: at most {LearningContextService.SUMMARY_SENTENCE_LIMIT} sentences.
  - Concepts: at most {LearningContextService.MAX_CONCEPTS}; include only the most reusable concepts.
  - Key theorems: at most {LearningContextService.MAX_KEY_THEOREMS}; prefer named or structurally central results.
  - Dependencies: at most {LearningContextService.MAX_DEPENDENCIES}; include prerequisites that help future chat/quiz context.

Chapter title:
{chapter_title}

Source chapter excerpt:
{raw_text.strip()}
""".strip()

    @staticmethod
    async def compile_chapter_learning(
        book_uuid: str,
        chapter_index: str,
        chapter_title: str,
        raw_text: str,
        translated_text: str,
        translator,
    ) -> dict[str, Any]:
        system_prompt = PromptRegistry.get(PromptId.LEARNING_CONTEXT).system
        user_prompt = LearningContextService.build_compile_prompt(chapter_title, raw_text, translated_text)
        context = None
        last_error: Exception | None = None
        for attempt in range(LearningContextService.COMPILE_MAX_RETRIES):
            prompt = user_prompt
            if attempt > 0:
                prompt = (
                    f"{user_prompt}\n\n"
                    "Your previous response could not be parsed as the required learning-context Markdown. "
                    "Return Markdown only with exactly these headings: "
                    "# Chapter Learning Context, ## Summary, ## Concepts, ## Key Theorems, ## Dependencies."
                )
            try:
                response = await translator.complete(prompt, system_prompt, temperature=0.3)
                parsed = LearningContextService.markdown_to_learning_context(response)
                if LearningContextService.is_learning_context_empty(parsed):
                    raise ValueError("No learning context sections found.")
                context = parsed
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Learning context compilation failed for chapter %s (attempt %s/%s): %s",
                    chapter_index,
                    attempt + 1,
                    LearningContextService.COMPILE_MAX_RETRIES,
                    exc,
                )
                if attempt < LearningContextService.COMPILE_MAX_RETRIES - 1:
                    await asyncio.sleep(2)

        if context is None:
            raise ValueError(f"Learning context compilation failed after retries: {last_error}")
        return await LearningContextService.save_learning_context(book_uuid, chapter_index, context)

    @staticmethod
    def load_learning_context(book_uuid: str, chapter_index: str) -> dict[str, Any]:
        path = BookStorage.learning_path(book_uuid, chapter_index)
        if path.exists():
            try:
                return LearningContextService.markdown_to_learning_context(path.read_text(encoding="utf-8"))
            except OSError:
                return LearningContextService.default_learning_context()

        return LearningContextService.default_learning_context()

    @staticmethod
    async def save_learning_context(book_uuid: str, chapter_index: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized = LearningContextService.normalize_learning_context(context)
        path = BookStorage.learning_path(book_uuid, chapter_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(LearningContextService.learning_context_to_markdown(normalized), encoding="utf-8")

        return normalized

    @staticmethod
    def format_chat_context(
        chapter_title: str,
        learning_context: dict[str, Any],
        selected_text: str = "",
    ) -> str:
        context = LearningContextService.normalize_learning_context(learning_context)
        parts = [f"Chapter: {chapter_title}"]

        if selected_text.strip():
            parts.extend(["Selected text:", selected_text.strip()])

        parts.extend(
            [
                "Chapter summary:",
                context["summary"] or "No chapter summary is available yet.",
                "Chapter concepts:",
                json.dumps(context["concepts"], ensure_ascii=False, indent=2),
                "Key theorems:",
                json.dumps(context["key_theorems"], ensure_ascii=False, indent=2),
                "Dependencies:",
                json.dumps(context["dependencies"], ensure_ascii=False, indent=2),
            ]
        )
        return "\n\n".join(parts)
