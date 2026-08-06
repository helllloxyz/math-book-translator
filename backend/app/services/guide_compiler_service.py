import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles

from app.services.book_storage import BookStorage
from app.services.chapter_source_service import ChapterSourceService
from app.services.llm_json import extract_json_candidate, parse_json_text
from app.services.prompts import PromptId, PromptRegistry
from app.services.translator import LLMConfigurationError


@dataclass
class _GuideChapterNode:
    index: str
    chapter: Any | None = None
    children: list["_GuideChapterNode"] = field(default_factory=list)
    order: int = 0


class GuideCompilerService:
    MAX_CHAPTER_GUIDES_PER_CHAPTER = 1
    MAX_DIRECTORY_GUIDES_PER_DIRECTORY = 1
    MAX_BOOK_GUIDES = 2
    MAX_CHAPTER_GUIDE_MARKDOWN_CHARS = 1200
    MAX_DIRECTORY_GUIDE_MARKDOWN_CHARS = 1800
    MAX_BOOK_GUIDE_MARKDOWN_CHARS = 2800
    MAX_MERMAID_NODES = 14
    MAX_MERMAID_EDGES = 18
    MAX_LLM_RETRIES = 3
    GUIDE_GENERATION_CONCURRENCY = 3

    @staticmethod
    def sanitize_guide_slug(slug: str) -> str:
        return BookStorage.sanitize_guide_slug(slug)

    @staticmethod
    def get_guide_dir(book_uuid: str) -> Path:
        return BookStorage.guide_dir(book_uuid)

    @staticmethod
    def get_guide_path(book_uuid: str, slug: str) -> Path:
        return BookStorage.guide_path(book_uuid, slug)

    @staticmethod
    def build_chapter_guide_prompt(book_title: str, chapter_context: dict[str, Any]) -> str:
        return f"""
You are creating chapter-level guides for a Top-Down reading workflow for an English mathematics book translated into Chinese.

Return strictly valid JSON:
{{
  "guides": [
    {{"slug": "preview", "title": "导读：读前 60 秒", "summary": "One short Chinese sentence locating this chapter.", "scope_type": "chapter", "scope_id": "{chapter_context.get("chapter_index", "")}", "markdown": "# 读前 60 秒\\n..."}}
  ]
}}

Requirements:
- Generate chapter-level guides only from the single chapter body provided below.
- Use `scope_type: "chapter"` and `scope_id` exactly equal to the provided `chapter_index`.
- At most {GuideCompilerService.MAX_CHAPTER_GUIDES_PER_CHAPTER} chapter guide for this chapter.
- Keep the guide markdown at most {GuideCompilerService.MAX_CHAPTER_GUIDE_MARKDOWN_CHARS} characters, including headings.
- This guide is a 60-second preview shown beside the chapter body, not a replacement explanation.
- Use exactly this compact structure:
  - `# 读前 60 秒`
  - `## 这一节要解决什么`: one or two short sentences.
  - `## 带着这些问题读`: two or three unanswered questions that direct attention while reading.
  - `## 阅读路线`: at most three one-sentence steps, describing what to skim, understand, and retain.
  - `## 卡住时回看`: at most three prerequisite cues; omit the section when none is essential.
- Do not create a concept glossary or a comprehensive summary.
- Do not restate theorem proofs, derivations, examples, or every formula from the chapter context.
- Mention each idea only once. Treat dependencies and concepts introduced in nearby chapters as background unless they are essential to entering this chapter.
- Prefer plain Chinese and at most one anchor formula for the whole guide.
- Do not use Mermaid diagrams in chapter-level guides.
- Do not include full original chapter text.
- Every claim must be grounded in the supplied body. Do not fill gaps from general knowledge.

Book title:
{book_title}

Single chapter body context:
{json.dumps(chapter_context, ensure_ascii=False, indent=2)}
""".strip()

    @staticmethod
    def build_book_guide_prompt(book_title: str, chapter_guide_inputs: list[dict[str, Any]]) -> str:
        return f"""
You are creating book-level guides for a Top-Down reading workflow for an English mathematics book translated into Chinese.

Return strictly valid JSON:
{{
  "guides": [
    {{"slug": "overview", "title": "导读一：全书核心问题", "summary": "One short Chinese summary of this guide.", "scope_type": "book", "scope_id": "book", "markdown": "# 导读一：全书核心问题\\n..."}}
  ]
}}

Requirements:
- Generate book-level guides for the whole book using only the generated top-level child guide summaries and metadata below.
- Use `scope_type: "book"` and `scope_id: "book"`.
- At most {GuideCompilerService.MAX_BOOK_GUIDES} book guide(s).
- Keep each guide markdown at most {GuideCompilerService.MAX_BOOK_GUIDE_MARKDOWN_CHARS} characters.
- Mermaid diagrams at most {GuideCompilerService.MAX_MERMAID_NODES} nodes and {GuideCompilerService.MAX_MERMAID_EDGES} edges.
- Explain the book's core theme, application background when available, historical development when available, core concepts, key theorem relationships, and chapter-by-chapter reading path.
- Do not include full chapter text.

Book title:
{book_title}

top_level_child_guide_inputs:
{json.dumps(chapter_guide_inputs, ensure_ascii=False, indent=2)}
""".strip()

    @staticmethod
    def build_directory_guide_prompt(
        book_title: str,
        directory_context: dict[str, Any],
        child_guide_inputs: list[dict[str, Any]],
    ) -> str:
        return f"""
You are creating directory-level guides for a Top-Down reading workflow for an English mathematics book translated into Chinese.

Return strictly valid JSON:
{{
  "guides": [
    {{"slug": "overview", "title": "导读：本节结构总览", "summary": "One short Chinese summary of this guide.", "scope_type": "directory", "scope_id": "{directory_context.get("directory_index", "")}", "markdown": "# 导读：本节结构总览\\n..."}}
  ]
}}

Requirements:
- Generate directory-level guides only for the single directory context provided below.
- Use `scope_type: "directory"` and `scope_id` exactly equal to the provided `directory_index`.
- Use the directory's own complete body when present and the direct child guide summaries below.
- At most {GuideCompilerService.MAX_DIRECTORY_GUIDES_PER_DIRECTORY} directory guide for this directory.
- Keep each guide markdown at most {GuideCompilerService.MAX_DIRECTORY_GUIDE_MARKDOWN_CHARS} characters.
- Do not use Mermaid diagrams in directory guides.
- Explain only this directory's role, how its direct children connect, and the recommended reading path across those children.
- Do not create a concept glossary or repeat the child summaries item by item.
- Do not include full child guide content or full chapter text.

Book title:
{book_title}

Directory context:
{json.dumps(directory_context, ensure_ascii=False, indent=2)}

direct_child_guide_inputs:
{json.dumps(child_guide_inputs, ensure_ascii=False, indent=2)}
""".strip()

    @staticmethod
    def build_top_down_prompt(book_title: str, chapter_contexts: list[dict[str, Any]]) -> str:
        top_level_guide_inputs = [
            {
                "child_index": context.get("chapter_index", ""),
                "child_title": context.get("title", ""),
                "summary": context.get("summary", ""),
            }
            for context in chapter_contexts
        ]
        return GuideCompilerService.build_book_guide_prompt(book_title, top_level_guide_inputs)

    @staticmethod
    def _markdown_preview(markdown: str, max_chars: int = 500) -> str:
        stripped = " ".join(markdown.split())
        if len(stripped) <= max_chars:
            return stripped
        return stripped[:max_chars].rstrip()

    def _node_guide_input(node: _GuideChapterNode, guide: dict[str, str]) -> dict[str, str]:
        return {
            "child_index": node.index,
            "child_title": GuideCompilerService._node_title(node),
            "scope_type": guide.get("scope_type", "chapter"),
            "scope_id": guide.get("scope_id", node.index),
            "slug": guide["slug"],
            "title": guide["title"],
            "summary": guide.get("summary") or GuideCompilerService._markdown_preview(guide.get("markdown", "")),
        }

    @staticmethod
    def _force_guide_scope(guide: dict[str, str], scope_type: str, scope_id: str) -> dict[str, str]:
        normalized = GuideCompilerService.normalize_guides(
            {
                "guides": [
                    {
                        **guide,
                        "scope_type": scope_type,
                        "scope_id": scope_id,
                    }
                ]
            }
        )
        return normalized[0] if normalized else guide

    @staticmethod
    def _truncate_markdown_at_line_boundary(markdown: str, max_chars: int) -> str:
        stripped = markdown.strip()
        if len(stripped) <= max_chars:
            return stripped

        kept_lines: list[str] = []
        current_length = 0
        for line in stripped.splitlines():
            added_length = len(line) + (1 if kept_lines else 0)
            if current_length + added_length > max_chars:
                break
            kept_lines.append(line)
            current_length += added_length
        return "\n".join(kept_lines).rstrip()

    @staticmethod
    def normalize_guides(data: Any) -> list[dict[str, str]] | None:
        guides = data.get("guides") if isinstance(data, dict) else None
        if not isinstance(guides, list):
            return None

        normalized = []
        for index, guide in enumerate(guides, start=1):
            if not isinstance(guide, dict):
                continue
            scope_type = str(guide.get("scope_type") or "book").strip().lower()
            if scope_type not in {"book", "chapter", "directory"}:
                scope_type = "book"
            scope_id = str(guide.get("scope_id") or ("book" if scope_type == "book" else "")).strip()
            if scope_type == "book":
                scope_id = "book"
            elif not scope_id:
                scope_id = str(index)
            slug = BookStorage.sanitize_guide_slug(str(guide.get("slug") or f"{index:02d}-guide"))
            filename = GuideCompilerService.guide_filename(scope_type, scope_id, slug)
            if scope_type == "chapter":
                source_type = "chapter_guide"
                source_id = f"guide:chapter:{scope_id}:{slug}"
            elif scope_type == "directory":
                source_type = "directory_guide"
                source_id = f"guide:directory:{scope_id}:{slug}"
            else:
                source_type = "book_guide"
                source_id = f"guide:book:{slug}"
            markdown = str(guide.get("markdown") or "")
            if scope_type == "chapter":
                markdown = GuideCompilerService._truncate_markdown_at_line_boundary(
                    markdown, GuideCompilerService.MAX_CHAPTER_GUIDE_MARKDOWN_CHARS
                )
            elif scope_type == "directory":
                markdown = GuideCompilerService._truncate_markdown_at_line_boundary(
                    markdown, GuideCompilerService.MAX_DIRECTORY_GUIDE_MARKDOWN_CHARS
                )
            else:
                markdown = GuideCompilerService._truncate_markdown_at_line_boundary(
                    markdown, GuideCompilerService.MAX_BOOK_GUIDE_MARKDOWN_CHARS
                )
            guide_data = {
                "slug": slug,
                "title": str(guide.get("title") or f"导读 {index}"),
                "scope_type": scope_type,
                "scope_id": scope_id,
                "filename": filename,
                "id": f"guide:{filename}",
                "source_type": source_type,
                "source_id": source_id,
                "markdown": markdown,
            }
            if guide.get("summary"):
                guide_data["summary"] = str(guide.get("summary"))
            normalized.append(guide_data)
        return normalized

    @staticmethod
    def guide_filename(scope_type: str, scope_id: str, slug: str) -> str:
        if scope_type == "chapter":
            safe_scope = BookStorage.sanitize_chapter_index(scope_id)
            return f"chapter-{safe_scope}-{slug}.md"
        if scope_type == "directory":
            safe_scope = BookStorage.sanitize_chapter_index(scope_id)
            return f"directory-{safe_scope}-{slug}.md"
        return f"{slug}.md"

    @staticmethod
    def parse_guides_candidate(text: str) -> list[dict[str, str]] | None:
        parsed = parse_json_text(text)
        return GuideCompilerService.normalize_guides(parsed)

    @staticmethod
    def is_guides_candidate(data: Any) -> bool:
        return GuideCompilerService.normalize_guides(data) is not None

    @staticmethod
    def extract_guides_json(text: str) -> list[dict[str, str]]:
        return extract_json_candidate(
            text,
            GuideCompilerService.is_guides_candidate,
            transform=GuideCompilerService.normalize_guides,
        )

    @staticmethod
    async def write_guides(
        book_uuid: str,
        guides: list[dict[str, str]],
        *,
        merge_manifest: bool = False,
    ) -> list[dict[str, str]]:
        normalized = GuideCompilerService.normalize_guides({"guides": guides}) or []
        manifest = []
        manifest_path = BookStorage.guide_manifest_path(book_uuid)
        if merge_manifest and manifest_path.exists():
            try:
                async with aiofiles.open(manifest_path, "r", encoding="utf-8") as handle:
                    existing = json.loads(await handle.read())
                if isinstance(existing, list):
                    manifest = [item for item in existing if isinstance(item, dict)]
            except (OSError, json.JSONDecodeError):
                manifest = []

        by_filename = {
            str(item.get("filename")): index
            for index, item in enumerate(manifest)
            if item.get("filename")
        }
        for guide in normalized:
            path = BookStorage._safe_book_subpath(book_uuid, "book_guides", guide["filename"])
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(path.suffix + ".tmp")
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as handle:
                await handle.write(guide["markdown"])
            temp_path.replace(path)
            item = {key: value for key, value in guide.items() if key != "markdown"}
            existing_index = by_filename.get(guide["filename"])
            if existing_index is None:
                by_filename[guide["filename"]] = len(manifest)
                manifest.append(item)
            else:
                manifest[existing_index] = item

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_temp_path = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        async with aiofiles.open(manifest_temp_path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(manifest, ensure_ascii=False, indent=2))
        manifest_temp_path.replace(manifest_path)
        return normalized

    @staticmethod
    async def _complete_guides(translator, user_prompt: str, system_prompt: str) -> list[dict[str, str]]:
        last_error: Exception | None = None
        for attempt in range(GuideCompilerService.MAX_LLM_RETRIES):
            try:
                response = await translator.complete(user_prompt, system_prompt, temperature=0.3)
                guides = GuideCompilerService.extract_guides_json(response)
                if not guides:
                    raise ValueError("Guide response did not contain any guides")
                return guides
            except LLMConfigurationError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < GuideCompilerService.MAX_LLM_RETRIES - 1:
                    await asyncio.sleep(1 + attempt)
        raise ValueError(
            f"Guide generation failed after {GuideCompilerService.MAX_LLM_RETRIES} attempts: {last_error}"
        ) from last_error

    @staticmethod
    def _chapter_index_sort_key(chapter_index: str) -> list[tuple[int, int, str]]:
        key = []
        for part in str(chapter_index or "").split("."):
            if part.isdigit():
                key.append((0, int(part), ""))
            else:
                key.append((1, 0, part.casefold()))
        return key

    @staticmethod
    def _ordered_chapters(chapters) -> list:
        return sorted(
            chapters,
            key=lambda chapter: (
                getattr(chapter, "order", None) is None,
                getattr(chapter, "order", None) or 0,
            ),
        )

    @staticmethod
    def _node_title(node: _GuideChapterNode) -> str:
        if node.chapter is not None:
            return str(node.chapter.title_zh or node.chapter.title_en or node.index)
        return node.index

    @staticmethod
    def _build_chapter_tree(chapters) -> list[_GuideChapterNode]:
        nodes: dict[str, _GuideChapterNode] = {}
        child_indexes_by_parent: dict[str | None, set[str]] = {}

        def get_node(index: str, order: int) -> _GuideChapterNode:
            node = nodes.get(index)
            if node is None:
                node = _GuideChapterNode(index=index, order=order)
                nodes[index] = node
            else:
                node.order = min(node.order, order)
            return node

        for order, chapter in enumerate(GuideCompilerService._ordered_chapters(chapters)):
            chapter_index = str(chapter.chapter_index or "").strip() or str(order + 1)
            parts = [part for part in chapter_index.split(".") if part]
            if not parts:
                parts = [str(order + 1)]

            for depth in range(1, len(parts) + 1):
                index = ".".join(parts[:depth])
                node = get_node(index, order)
                if depth == len(parts):
                    node.chapter = chapter
                parent_index = ".".join(parts[: depth - 1]) if depth > 1 else None
                child_indexes_by_parent.setdefault(parent_index, set()).add(index)

        for parent_index, child_indexes in child_indexes_by_parent.items():
            if parent_index is None:
                continue
            parent = nodes[parent_index]
            parent.children = [nodes[index] for index in child_indexes]

        for node in nodes.values():
            node.children.sort(key=lambda child: (child.order, GuideCompilerService._chapter_index_sort_key(child.index)))

        roots = [nodes[index] for index in child_indexes_by_parent.get(None, set())]
        roots.sort(key=lambda node: (node.order, GuideCompilerService._chapter_index_sort_key(node.index)))
        return roots

    @staticmethod
    async def generate_top_down_guides(book, chapters, translator) -> list[dict[str, str]]:
        system_prompt = PromptRegistry.get(PromptId.TOP_DOWN_GUIDE).system
        request_semaphore = asyncio.Semaphore(GuideCompilerService.GUIDE_GENERATION_CONCURRENCY)
        checkpoint_lock = asyncio.Lock()

        async def complete_guides(user_prompt: str) -> list[dict[str, str]]:
            async with request_semaphore:
                return await GuideCompilerService._complete_guides(translator, user_prompt, system_prompt)

        async def checkpoint(guides: list[dict[str, str]]) -> None:
            if not guides:
                return
            async with checkpoint_lock:
                await GuideCompilerService.write_guides(book.uuid, guides, merge_manifest=True)

        async def generate_node_guides(
            node: _GuideChapterNode,
        ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
            if not node.children:
                if node.chapter is None:
                    return [], []
                chapter = node.chapter
                chapter_context = await ChapterSourceService.chapter_context(
                    book.uuid,
                    chapter,
                )
                if not chapter_context["body"]:
                    return [], []
                user_prompt = GuideCompilerService.build_chapter_guide_prompt(book.title, chapter_context)
                guides = [
                    GuideCompilerService._force_guide_scope(guide, "chapter", str(chapter.chapter_index))
                    for guide in await complete_guides(user_prompt)
                ]
                await checkpoint(guides)
                return guides, guides

            child_guide_inputs: list[dict[str, str]] = []
            subtree_guides: list[dict[str, str]] = []
            child_results = await asyncio.gather(
                *(generate_node_guides(child) for child in node.children)
            )
            for child, (child_guides, child_subtree_guides) in zip(node.children, child_results):
                child_guide_inputs.extend(
                    GuideCompilerService._node_guide_input(child, guide)
                    for guide in child_guides
                )
                subtree_guides.extend(child_subtree_guides)

            directory_context = {
                "directory_index": node.index,
                "title": GuideCompilerService._node_title(node),
            }
            if node.chapter is not None:
                own_context = await ChapterSourceService.chapter_context(
                    book.uuid,
                    node.chapter,
                )
                directory_context.update(
                    {
                        "body_language": own_context["body_language"],
                        "body": own_context["body"],
                    }
                )
            if not child_guide_inputs and not directory_context.get("body"):
                return [], subtree_guides
            user_prompt = GuideCompilerService.build_directory_guide_prompt(
                book.title,
                directory_context,
                child_guide_inputs,
            )
            guides = [
                GuideCompilerService._force_guide_scope(guide, "directory", node.index)
                for guide in await complete_guides(user_prompt)
            ]
            await checkpoint(guides)
            return guides, [*subtree_guides, *guides]

        roots = GuideCompilerService._build_chapter_tree(chapters)
        top_level_guide_inputs: list[dict[str, str]] = []
        generated_guides: list[dict[str, str]] = []
        root_results = await asyncio.gather(*(generate_node_guides(root) for root in roots))
        for root, (root_guides, root_subtree_guides) in zip(roots, root_results):
            top_level_guide_inputs.extend(
                GuideCompilerService._node_guide_input(root, guide)
                for guide in root_guides
            )
            generated_guides.extend(root_subtree_guides)

        if not top_level_guide_inputs:
            return await GuideCompilerService.write_guides(book.uuid, generated_guides)
        user_prompt = GuideCompilerService.build_book_guide_prompt(book.title, top_level_guide_inputs)
        book_guides = [
            GuideCompilerService._force_guide_scope(guide, "book", "book")
            for guide in await complete_guides(user_prompt)
        ]
        await checkpoint(book_guides)
        guides = [*generated_guides, *book_guides]
        return await GuideCompilerService.write_guides(book.uuid, guides)

    @staticmethod
    async def generate_chapter_guide(book, chapter, translator) -> list[dict[str, str]]:
        """Generate or replace the compact guide belonging to one chapter only."""
        chapter_context = await ChapterSourceService.chapter_context(book.uuid, chapter)
        if not chapter_context["body"]:
            raise ValueError("Chapter body is missing")

        system_prompt = PromptRegistry.get(PromptId.TOP_DOWN_GUIDE).system
        user_prompt = GuideCompilerService.build_chapter_guide_prompt(book.title, chapter_context)
        guides = [
            GuideCompilerService._force_guide_scope(
                guide,
                "chapter",
                str(chapter.chapter_index),
            )
            for guide in await GuideCompilerService._complete_guides(
                translator,
                user_prompt,
                system_prompt,
            )
        ]
        return await GuideCompilerService.write_guides(
            book.uuid,
            guides,
            merge_manifest=True,
        )
