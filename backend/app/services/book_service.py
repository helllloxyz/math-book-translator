import json
import os
import uuid
import shutil
import logging
import asyncio
import re
import tempfile
import zipfile
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, UploadFile
from app.models.schema import Book, Chapter, BookStatus, UserNote
from app.models.base import SessionLocal
from app.services.book_storage import BookStorage
from app.services.guide_compiler_service import GuideCompilerService
from app.services.llm_json import extract_json_candidate
from app.services.parser import MarkdownSplitter
from app.services.prompts import PromptId, PromptRegistry
from app.services.translator import LLMConfigurationError, TranslatorService

logger = logging.getLogger("app.book_service")

MAX_CHAPTER_CHARS = 80000
MIN_CHAPTER_WARNING_CHARS = 30
PACKAGE_UUID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,127}$")


@dataclass
class TranslationPlan:
    total: int
    completed: int
    pending: list[Chapter]
    failed: int = 0


class BookService:
    _translation_locks: dict[int, asyncio.Lock] = {}

    CHAPTER_CONTENT_TYPE_LABELS = {
        "main_text": "正文",
        "exercise": "习题",
        "example": "例题",
        "appendix": "附录",
        "preface": "前言/目录",
        "reference": "参考/索引",
    }

    CONTENT_TYPE_PATTERNS = (
        (
            "exercise",
            (
                r"\b(exercises?|problems?|problem\s+sets?|review\s+problems?|supplementary\s+problems?|"
                r"selected\s+exercises?|miscellaneous\s+problems?|challenge\s+questions?|practice|drills?|"
                r"questions?|worksheet|homework|solutions?\s+to\s+exercises?)\b",
                r"(习题|练习题|课后练习|补充练习|综合练习|复习题|思考题|挑战题|问题集|作业题|训练题|题解|解答)",
            ),
        ),
        (
            "example",
            (
                r"\b(examples?|worked\s+examples?|sample\s+problems?|solutions?)\b",
                r"(例题|例子|范例|例解|解例|典型例题)",
            ),
        ),
        (
            "appendix",
            (
                r"\b(appendix|appendices)\b",
                r"(附录|附表)",
            ),
        ),
        (
            "reference",
            (
                r"\b(references?|bibliography|further\s+reading|recommended\s+reading|index|notation|"
                r"symbols?|glossary|errata)\b",
                r"(参考文献|参考资料|延伸阅读|索引|符号表|记号表|术语表|勘误)",
            ),
        ),
        (
            "preface",
            (
                r"\b(preface|foreword|introduction\s+to\s+the\s+book|contents?|table\s+of\s+contents|"
                r"acknowledg(e)?ments?|about\s+the\s+author)\b",
                r"(前言|序言|序|目录|致谢|作者简介|导言)",
            ),
        ),
    )

    @staticmethod
    def _classification_text(title: str, content: str = "") -> str:
        signals = [str(title or "")]
        for line in str(content or "").splitlines()[:20]:
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^#{1,6}\s+", stripped):
                signals.append(stripped)
                continue
            if len(signals) == 1:
                signals.append(stripped[:120])
            if len(signals) >= 4:
                break
        return " ".join(signals).casefold()

    @staticmethod
    def classify_chapter_content_type(title: str, content: str = "") -> str:
        haystack = BookService._classification_text(title, content)
        for content_type, patterns in BookService.CONTENT_TYPE_PATTERNS:
            if any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in patterns):
                return content_type
        return "main_text"

    @staticmethod
    def build_import_chapter_preview(chunks: list[dict]) -> list[dict]:
        preview = []
        for chunk in chunks:
            content = chunk.get("content") or ""
            content_type = chunk.get("content_type") or BookService.classify_chapter_content_type(
                chunk.get("title") or "",
                content,
            )
            preview.append(
                {
                    "chapter_index": str(chunk.get("chapter_index") or "").strip() or "?",
                    "title": " ".join(str(chunk.get("title") or "").split()) or "Untitled",
                    "char_count": len(content),
                    "content_type": content_type,
                    "content_type_label": BookService.CHAPTER_CONTENT_TYPE_LABELS.get(content_type, content_type),
                }
            )
        return preview

    @staticmethod
    def build_import_outline_confirmation(filename: str, content: str) -> dict:
        splitter = MarkdownSplitter()
        outline = splitter.analyze_outline(content)
        default_outline_plan = {
            "import_depth": outline.get("default_import_depth", 1),
            "nodes": [
                {"id": node["id"], "split_level": node.get("split_level")}
                for node in outline.get("nodes", [])
            ],
        }
        return {
            "requires_confirmation": True,
            "confirmation_type": "outline",
            "message": "Confirm the detected chapter outline before importing.",
            "outline": {
                **outline,
                "filename": filename,
                "recommendation": "请确认哪些标题作为切分点；默认按检测到的最低编号层级切分。",
                "default_outline_plan": default_outline_plan,
            },
        }

    @staticmethod
    def build_import_preflight_chapter_table(chunks: list[dict]) -> str:
        lines = ["Chapter list:"]
        for chapter in BookService.build_import_chapter_preview(chunks):
            lines.append(
                f"{chapter['chapter_index']} | {chapter['title']} | "
                f"{chapter['content_type']} | {chapter['char_count']} chars"
            )
        return "\n".join(lines)

    @staticmethod
    def _normalize_import_preflight_result(value: dict) -> dict:
        severity = str(value.get("severity", "ok")).lower()
        if severity not in {"ok", "warning", "blocked"}:
            severity = "warning"
        raw_issues = value.get("issues", [])
        issues = []
        if isinstance(raw_issues, list):
            for issue in raw_issues:
                if isinstance(issue, dict):
                    issues.append(
                        {
                            "code": str(issue.get("code") or "issue"),
                            "message": str(issue.get("message") or issue.get("detail") or "Import preflight issue."),
                        }
                    )
                elif issue:
                    issues.append({"code": "issue", "message": str(issue)})
        return {
            "severity": severity,
            "issues": issues,
            "recommendation": str(value.get("recommendation") or ""),
        }

    @staticmethod
    def _chapter_index_sort_key(chapter_index: str) -> tuple:
        parts = []
        for part in str(chapter_index or "").split("."):
            if part.isdigit():
                parts.append((0, int(part)))
            else:
                parts.append((1, part))
        return tuple(parts)

    @staticmethod
    def run_import_local_preflight(chunks: list[dict]) -> dict:
        issues = []
        recommendation = "章节序列看起来可用。请确认预览与原书目录一致后继续导入。"

        seen_indexes: dict[str, list[dict]] = {}
        for chunk in chunks:
            chapter_index = str(chunk.get("chapter_index") or "?").strip() or "?"
            seen_indexes.setdefault(chapter_index, []).append(chunk)

        duplicate_indexes = [
            (chapter_index, duplicate_chunks)
            for chapter_index, duplicate_chunks in seen_indexes.items()
            if len(duplicate_chunks) > 1
        ]
        if duplicate_indexes:
            examples = []
            for chapter_index, duplicate_chunks in duplicate_indexes[:5]:
                titles = [
                    " ".join(str(chunk.get("title") or "Untitled").split())
                    for chunk in duplicate_chunks[:2]
                ]
                examples.append(f"{chapter_index}: {' / '.join(titles)}")
            suffix = "" if len(duplicate_indexes) <= 5 else "，下面显示前 5 组"
            issues.append(
                {
                    "code": "duplicate_chapter_indexes",
                    "message": f"发现 {len(duplicate_indexes)} 组重复章节编号{suffix}。",
                    "examples": examples,
                }
            )

        previous_key = None
        previous_index = None
        inversions = []
        for chunk in chunks:
            chapter_index = str(chunk.get("chapter_index") or "?").strip() or "?"
            current_key = BookService._chapter_index_sort_key(chapter_index)
            if previous_key is not None and current_key < previous_key:
                inversions.append(f"{previous_index} -> {chapter_index}")
            previous_key = current_key
            previous_index = chapter_index
        if inversions:
            suffix = "" if len(inversions) <= 5 else "，下面显示前 5 处"
            issues.append(
                {
                    "code": "chapter_index_order",
                    "message": f"章节编号顺序不连续或倒置，共 {len(inversions)} 处{suffix}。",
                    "examples": inversions[:5],
                }
            )

        short_chapters = []
        for chunk in chunks:
            char_count = len(chunk.get("content") or "")
            if char_count < MIN_CHAPTER_WARNING_CHARS:
                chapter_index = str(chunk.get("chapter_index") or "?").strip() or "?"
                title = " ".join(str(chunk.get("title") or "Untitled").split())
                short_chapters.append(f"{chapter_index} {title} ({char_count} chars)")
        if short_chapters:
            suffix = "" if len(short_chapters) <= 8 else "，下面显示前 8 个"
            issues.append(
                {
                    "code": "chapter_too_short",
                    "message": f"发现 {len(short_chapters)} 个少于 {MIN_CHAPTER_WARNING_CHARS} 个字符的近空章节{suffix}。",
                    "examples": short_chapters[:8],
                }
            )

        if issues:
            recommendation = "导入前请重点检查重复编号、章节顺序和近空章节。"

        return {
            "severity": "warning" if issues else "ok",
            "issues": issues,
            "recommendation": recommendation,
            "chapters": BookService.build_import_chapter_preview(chunks),
        }

    @staticmethod
    def run_import_hard_block(chunks: list[dict]) -> dict | None:
        issues = []
        for chunk in chunks:
            char_count = len(chunk.get("content") or "")
            if char_count > MAX_CHAPTER_CHARS:
                chapter_index = str(chunk.get("chapter_index") or "?")
                title = str(chunk.get("title") or "Untitled")
                issues.append(
                    {
                        "code": "chapter_too_large",
                        "message": (
                            f"Chapter {chapter_index} ({title}) has {char_count} characters, "
                            f"which exceeds the {MAX_CHAPTER_CHARS} character limit."
                        ),
                    }
                )
        if not issues:
            return None
        return {
            "severity": "blocked",
            "issues": issues,
            "recommendation": "导入前请先拆分超长章节。",
        }

    @staticmethod
    async def run_import_preflight(chunks: list[dict]) -> dict:
        hard_block = BookService.run_import_hard_block(chunks)
        if hard_block:
            hard_block["chapters"] = BookService.build_import_chapter_preview(chunks)
            return hard_block

        local_preflight = BookService.run_import_local_preflight(chunks)
        if local_preflight["severity"] != "ok" or os.getenv("IMPORT_PREFLIGHT_LLM", "").lower() not in {"1", "true", "yes"}:
            return local_preflight

        translator = TranslatorService(task="import_preflight")
        if not getattr(translator, "api_key", None):
            return local_preflight

        prompt = BookService.build_import_preflight_chapter_table(chunks)
        system_prompt = PromptRegistry.get(PromptId.IMPORT_PREFLIGHT).system
        raw_response = ""
        try:
            raw_response = await translator.complete(prompt, system_prompt, temperature=0.1)
            parsed = extract_json_candidate(raw_response, validator=lambda value: isinstance(value, dict))
            normalized = BookService._normalize_import_preflight_result(parsed)
            normalized["chapters"] = BookService.build_import_chapter_preview(chunks)
            return normalized
        except Exception as exc:
            logger.warning(
                "Import preflight LLM review failed: %s (response_chars=%s)",
                exc,
                len(raw_response),
            )
            return {
                **local_preflight,
                "recommendation": "LLM 导入预检不可用；本地检查已通过。",
            }

    @staticmethod
    def get_chapter_filenames(book_uuid: str, chapter_index: str):
        return (
            str(BookStorage.raw_chapter_path(book_uuid, chapter_index)),
            str(BookStorage.translated_chapter_path(book_uuid, chapter_index)),
        )

    @staticmethod
    async def save_meta_json(book_dir: str | Path, book: Book, chapters: list[Chapter]):
        meta = {
            "uuid": book.uuid,
            "title": book.title,
            "original_filename": book.original_filename,
            "chapters": [
                {
                    "chapter_index": c.chapter_index,
                    "title_en": c.title_en,
                    "content_type": c.content_type or "main_text",
                    "order": c.order
                }
                for c in chapters
            ]
        }
        meta_path = Path(book_dir) / "meta.json"
        try:
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info(f"Saved meta.json for book {book.title}")
        except Exception as e:
            logger.error(f"Failed to save meta.json: {e}")

    @staticmethod
    def sync_meta_json_title(book_dir: str | Path, book: Book) -> bool:
        meta_path = Path(book_dir) / "meta.json"
        if not meta_path.is_file():
            return False
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                logger.warning("Skipped title sync because meta.json is not an object: %s", meta_path)
                return False
            if meta.get("title") == book.title:
                return False
            meta["title"] = book.title
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception as exc:
            logger.warning("Failed to sync meta.json title for book %s: %s", book.uuid, exc)
            return False

    @staticmethod
    async def import_preprocessed_book(source_dir: str, meta_path: str, db: AsyncSession):
        logger.info(f"Importing preprocessed book from {source_dir}")
        source_dir_path = Path(source_dir)
        try:
            content = Path(meta_path).read_text(encoding="utf-8")
            meta = json.loads(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read meta.json: {e}")

        BookStorage.ensure_book_dirs(root=source_dir_path)

        new_uuid = source_dir_path.name
        new_book = Book(
            uuid=new_uuid,
            title=meta.get("title", "Imported Book"),
            original_filename=meta.get("original_filename", "imported.md"),
            status=BookStatus.loaded
        )
        db.add(new_book)
        await db.commit()
        await db.refresh(new_book)
        
        chapters_data = meta.get("chapters", [])
        new_chapters = []
        for c_data in chapters_data:
            ch = Chapter(
                book_id=new_book.id,
                chapter_index=c_data["chapter_index"],
                title_en=c_data["title_en"],
                content_type=c_data.get("content_type") or "main_text",
                order=c_data["order"]
            )
            db.add(ch)
            new_chapters.append(ch)
        
        await db.commit()
        plan = await BookService.build_translation_plan(new_book, new_chapters)
        new_book.translation_total = plan.total
        new_book.translation_completed = plan.completed
        new_book.translation_failed = plan.failed
        new_book.status = BookStatus.translated if plan.total and plan.completed == plan.total else BookStatus.loaded
        await db.commit()
        return {
            "message": "Preprocessed book imported successfully",
            "book_id": new_book.id,
            "total_chapters": len(new_chapters)
        }

    @staticmethod
    def _safe_package_filename(title: str, book_uuid: str) -> str:
        stem = BookStorage._INVALID_FILENAME_CHARS.sub("_", str(title or "book")).strip("._ ")
        if not stem:
            stem = "book"
        return f"{stem}-{book_uuid}.zip"

    @staticmethod
    def _validate_package_uuid(raw_uuid: str | None) -> str:
        package_uuid = str(raw_uuid or "").strip()
        if not package_uuid or not PACKAGE_UUID_RE.fullmatch(package_uuid):
            raise HTTPException(status_code=400, detail="Invalid package uuid")
        if Path(package_uuid).name != package_uuid or "/" in package_uuid or "\\" in package_uuid:
            raise HTTPException(status_code=400, detail="Invalid package uuid")
        return package_uuid

    @staticmethod
    def _validate_zip_members(package_zip: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        safe_members = []
        for member in package_zip.infolist():
            name = member.filename
            if not name or "\x00" in name or "\\" in name:
                raise HTTPException(status_code=400, detail="Package contains an unsafe path")
            member_path = Path(name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise HTTPException(status_code=400, detail="Package contains an unsafe path")
            safe_members.append(member)
        return safe_members

    @staticmethod
    def _package_content_root(extract_root: Path) -> tuple[Path, Path]:
        meta_path = extract_root / "meta.json"
        if meta_path.is_file():
            return extract_root, meta_path

        top_dirs = [path for path in extract_root.iterdir() if path.is_dir()]
        top_files = [path for path in extract_root.iterdir() if path.is_file()]
        if len(top_dirs) == 1 and not top_files:
            nested_meta = top_dirs[0] / "meta.json"
            if nested_meta.is_file():
                return top_dirs[0], nested_meta

        raise HTTPException(status_code=400, detail="Package must contain meta.json at the root or inside one top-level directory")

    @staticmethod
    def _load_package_meta(meta_path: Path) -> dict:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to read meta.json: {exc}")

        if not isinstance(meta, dict):
            raise HTTPException(status_code=400, detail="Package meta.json must contain an object")
        chapters = meta.get("chapters")
        if not isinstance(chapters, list) or not chapters:
            raise HTTPException(status_code=400, detail="Package meta.json must contain a non-empty chapters list")
        required = {"chapter_index", "title_en", "order"}
        for index, chapter in enumerate(chapters, start=1):
            if not isinstance(chapter, dict) or not required.issubset(chapter):
                raise HTTPException(status_code=400, detail=f"Package meta.json chapter {index} is invalid")
        return meta

    @staticmethod
    async def build_book_package(book_id: int, db: AsyncSession) -> tuple[BytesIO, str]:
        result = await db.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        book_dir = BookStorage.book_dir(book.uuid)
        if not book_dir.exists() or not book_dir.is_dir():
            raise HTTPException(status_code=404, detail="Book storage directory not found")

        BookService.sync_meta_json_title(book_dir, book)

        package_buffer = BytesIO()
        with zipfile.ZipFile(package_buffer, "w", compression=zipfile.ZIP_DEFLATED) as package_zip:
            for path in sorted(book_dir.rglob("*")):
                if not path.is_file():
                    continue
                if path.relative_to(book_dir).parts[0] == "book_learning":
                    continue
                if path.name.endswith(".tmp") or path.name.startswith("."):
                    continue
                resolved = path.resolve()
                try:
                    resolved.relative_to(book_dir.resolve())
                except ValueError:
                    continue
                arcname = Path(book.uuid) / path.relative_to(book_dir)
                package_zip.write(path, arcname.as_posix())
        package_buffer.seek(0)
        return package_buffer, BookService._safe_package_filename(book.title, book.uuid)

    @staticmethod
    async def import_book_package(file: UploadFile, db: AsyncSession):
        filename = file.filename or ""
        if not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only .zip packages are supported")

        package_bytes = await file.read()
        if not package_bytes:
            raise HTTPException(status_code=400, detail="Package is empty")

        storage_dir = BookStorage.storage_dir()
        storage_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="book-package-", dir=storage_dir) as temp_dir:
            temp_path = Path(temp_dir)
            try:
                with zipfile.ZipFile(BytesIO(package_bytes)) as package_zip:
                    safe_members = BookService._validate_zip_members(package_zip)
                    package_zip.extractall(temp_path, members=safe_members)
            except BadZipFile:
                raise HTTPException(status_code=400, detail="Invalid zip package")

            content_root, meta_path = BookService._package_content_root(temp_path)
            meta = BookService._load_package_meta(meta_path)
            top_level_uuid = content_root.name if content_root != temp_path else None
            meta_uuid = meta.get("uuid")
            if meta_uuid and top_level_uuid and str(meta_uuid) != top_level_uuid:
                raise HTTPException(status_code=400, detail="Package uuid does not match its top-level directory")
            package_uuid = BookService._validate_package_uuid(meta_uuid or top_level_uuid)

            existing = await db.execute(select(Book).where(Book.uuid == package_uuid))
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=409, detail="A book with this package uuid already exists")

            destination = BookStorage.book_dir(package_uuid)
            if destination.exists():
                raise HTTPException(status_code=409, detail="A storage directory with this package uuid already exists")

            final_source = temp_path / package_uuid
            if content_root == temp_path:
                final_source.mkdir()
                for child in list(temp_path.iterdir()):
                    if child == final_source:
                        continue
                    shutil.move(str(child), str(final_source / child.name))
            elif content_root != final_source:
                content_root.rename(final_source)
            shutil.move(str(final_source), str(destination))

            try:
                return await BookService.import_preprocessed_book(str(destination), str(destination / "meta.json"), db)
            except Exception:
                if destination.exists():
                    shutil.rmtree(destination)
                raise

    @staticmethod
    def get_translation_concurrency() -> int:
        raw_value = os.getenv("TRANSLATION_CONCURRENCY", "5")
        try:
            return max(1, int(raw_value))
        except ValueError:
            logger.warning("Invalid TRANSLATION_CONCURRENCY=%s; using 5", raw_value)
            return 5

    @staticmethod
    async def build_translation_plan(book, chapters) -> TranslationPlan:
        total = 0
        completed = 0
        pending = []

        for chapter in chapters:
            raw_path = BookStorage.raw_chapter_path(book.uuid, chapter.chapter_index)
            trans_path = BookStorage.translated_chapter_path(book.uuid, chapter.chapter_index)
            if not raw_path.exists():
                continue

            content_raw = raw_path.read_text(encoding="utf-8")
            if not content_raw.strip():
                continue

            total += 1
            if trans_path.exists() and trans_path.stat().st_size > 0:
                completed += 1
            else:
                pending.append(chapter)

        return TranslationPlan(total=total, completed=completed, pending=pending)

    @staticmethod
    async def require_translation_configuration(book, chapters) -> TranslationPlan:
        plan = await BookService.build_translation_plan(book, chapters)
        if plan.pending:
            TranslatorService.require_configured(task="translation")
        elif plan.total:
            TranslatorService.require_configured(task="guides")
        return plan

    @staticmethod
    async def _translate_one_chapter(book, chapter, translator, *, force: bool = False) -> bool:
        raw_path = BookStorage.raw_chapter_path(book.uuid, chapter.chapter_index)
        trans_path = BookStorage.translated_chapter_path(book.uuid, chapter.chapter_index)
        if not force and trans_path.exists() and trans_path.stat().st_size > 0:
            return True
        if not raw_path.exists():
            return False

        content_raw = raw_path.read_text(encoding="utf-8")
        if not content_raw.strip():
            return True

        max_retries = 3
        translated_text = None
        for attempt in range(max_retries):
            try:
                translated_text = await translator.translate_text(content_raw)
                break
            except Exception as exc:
                logger.warning(
                    "Translation failed for chapter %s (attempt %s/%s): %s",
                    chapter.chapter_index,
                    attempt + 1,
                    max_retries,
                    exc,
                )
                if isinstance(exc, LLMConfigurationError):
                    break
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)

        if not translated_text:
            return False

        if not force and trans_path.exists() and trans_path.stat().st_size > 0:
            return True

        trans_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = trans_path.with_suffix(trans_path.suffix + ".tmp")
        temp_path.write_text(translated_text, encoding="utf-8")
        temp_path.replace(trans_path)
        return True

    @staticmethod
    async def process_chapter_retranslation(book_id: int, chapter_id: int) -> None:
        """Atomically replace one translation while keeping the prior file on failure."""
        lock = BookService._translation_locks.setdefault(book_id, asyncio.Lock())
        if lock.locked():
            logger.info("Translation task already running for Book ID: %s", book_id)
            return

        async with lock:
            async with SessionLocal() as session:
                book = await session.scalar(select(Book).where(Book.id == book_id))
                chapter = await session.scalar(
                    select(Chapter).where(Chapter.id == chapter_id, Chapter.book_id == book_id)
                )
                if not book or not chapter:
                    return
                previous_status = book.status
                try:
                    TranslatorService.require_configured(task="translation")
                    book.status = BookStatus.translating
                    await session.commit()
                    success = await BookService._translate_one_chapter(
                        book,
                        chapter,
                        TranslatorService(task="translation"),
                        force=True,
                    )
                    # Relationships are not eagerly loaded in background sessions, so query explicitly.
                    chapters = list(
                        (
                            await session.execute(
                                select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order)
                            )
                        ).scalars().all()
                    )
                    plan = await BookService.build_translation_plan(book, chapters)
                    book.translation_total = plan.total
                    book.translation_completed = plan.completed
                    book.translation_failed = 0 if success else 1
                    book.status = BookStatus.translated if success and plan.completed == plan.total else BookStatus.failed
                    await session.commit()
                except Exception:
                    logger.exception(
                        "Chapter retranslation failed book=%s chapter=%s", book_id, chapter_id
                    )
                    book.status = BookStatus.failed if previous_status != BookStatus.loaded else previous_status
                    await session.commit()

    @staticmethod
    async def translate_pending_chapters(
        book,
        chapters,
        translator,
        *,
        concurrency: int | None = None,
        on_progress=None,
    ) -> TranslationPlan:
        plan = await BookService.build_translation_plan(book, chapters)
        if not plan.pending:
            return plan

        semaphore = asyncio.Semaphore(concurrency or BookService.get_translation_concurrency())
        progress_lock = asyncio.Lock()
        completed = plan.completed
        failed = 0

        async def run_chapter(chapter):
            nonlocal completed, failed
            async with semaphore:
                logger.info("Translating Chapter %s", chapter.chapter_index)
                success = await BookService._translate_one_chapter(book, chapter, translator)

            async with progress_lock:
                if success:
                    completed += 1
                else:
                    failed += 1
                if on_progress:
                    maybe_awaitable = on_progress(completed, plan.total, failed)
                    if asyncio.iscoroutine(maybe_awaitable):
                        await maybe_awaitable

        await asyncio.gather(*(run_chapter(chapter) for chapter in plan.pending))
        return TranslationPlan(total=plan.total, completed=completed, pending=[], failed=failed)

    @staticmethod
    async def generate_guides_for_translated_book(book, chapters, translator, session, book_id: int) -> None:
        book.status = BookStatus.generating_guides
        await session.commit()
        try:
            await GuideCompilerService.generate_top_down_guides(book, chapters, translator)
        except Exception:
            logger.exception("Top-down guide generation failed for book %s", book_id)
            raise

    @staticmethod
    async def process_book_translation(book_id: int):
        logger.info(f"Background task started for Book ID: {book_id}")
        lock = BookService._translation_locks.setdefault(book_id, asyncio.Lock())
        if lock.locked():
            logger.info("Translation task already running for Book ID: %s", book_id)
            return

        async with lock:
            await BookService._process_book_translation_locked(book_id)

    @staticmethod
    async def _process_book_translation_locked(book_id: int):
        async with SessionLocal() as session:
            result = await session.execute(select(Book).where(Book.id == book_id))
            book = result.scalar_one_or_none()
            if not book:
                logger.error(f"Book ID {book_id} not found.")
                return

            result = await session.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order))
            chapters = result.scalars().all()
            
            try:
                initial_plan = await BookService.require_translation_configuration(book, chapters)
                book.translation_total = initial_plan.total
                book.translation_completed = initial_plan.completed
                book.translation_failed = initial_plan.failed
                if not initial_plan.pending:
                    if initial_plan.total:
                        guide_translator = TranslatorService(task="guides")
                        await BookService.generate_guides_for_translated_book(
                            book, chapters, guide_translator, session, book_id
                        )
                        book.status = BookStatus.translated
                    else:
                        book.status = BookStatus.loaded
                    await session.commit()
                    return

                translator = TranslatorService(task="translation")
                book.status = BookStatus.translating
                await session.commit()

                async def update_progress(completed: int, total: int, failed: int):
                    book.translation_completed = completed
                    book.translation_total = total
                    book.translation_failed = failed
                    await session.commit()

                final_plan = await BookService.translate_pending_chapters(
                    book,
                    chapters,
                    translator,
                    on_progress=update_progress,
                )
                book.translation_total = final_plan.total
                book.translation_completed = final_plan.completed
                book.translation_failed = final_plan.failed
                if final_plan.failed == 0 and final_plan.completed == final_plan.total:
                    guide_translator = TranslatorService(task="guides")
                    await BookService.generate_guides_for_translated_book(
                        book, chapters, guide_translator, session, book_id
                    )
                    book.status = BookStatus.translated
                else:
                    book.status = BookStatus.failed
                await session.commit()
            except Exception as e:
                logger.error(f"Error processing book {book_id}: {e}", exc_info=True)
                book.status = BookStatus.failed
                await session.commit()

    @staticmethod
    async def handle_book_import(
        source_path: str,
        db: AsyncSession,
        *,
        force: bool = False,
        preflight: bool = True,
        outline_selection: list[str] | None = None,
        outline_plan: dict | None = None,
    ):
        import_type, source, meta_path = BookService.resolve_import_source(source_path)
        if import_type == "preprocessed":
            return await BookService.import_preprocessed_book(str(source), str(meta_path), db)

        content = source.read_text(encoding="utf-8")
        
        return await BookService.create_book_from_content(
            source.name,
            content, 
            db, 
            source_dir=str(source.parent),
            force=force,
            preflight=preflight,
            outline_selection=outline_selection,
            outline_plan=outline_plan,
        )

    @staticmethod
    def resolve_import_source(source_path: str) -> tuple[str, Path, Path | None]:
        source_path = source_path.strip()
        # WSL Path Conversion
        if Path("/").anchor == "/" and ':' in source_path and '\\' in source_path:
            import re
            drive_match = re.match(r'^([a-zA-Z]):\\(.*)', source_path)
            if drive_match:
                drive_letter = drive_match.group(1).lower()
                relative_path = drive_match.group(2).replace('\\', '/')
                source_path = f"/mnt/{drive_letter}/{relative_path}"

        source = Path(source_path)

        if source.is_dir():
            meta_path = source / "meta.json"
            if meta_path.exists():
                return "preprocessed", source, meta_path
            full_md_path = source / "full.md"
            if full_md_path.exists() and full_md_path.is_file():
                return "markdown", full_md_path, None
            else:
                raise HTTPException(status_code=400, detail="目录中没有找到 meta.json 或 full.md。")

        if not source.exists() or source.suffix != ".md":
            raise HTTPException(status_code=400, detail="请输入有效的 Markdown 文件路径，或包含 full.md 的目录路径。")

        return "markdown", source, None

    @staticmethod
    async def create_book_from_content(
        filename: str,
        content: str,
        db: AsyncSession,
        source_dir: str = None,
        *,
        force: bool = False,
        preflight: bool = True,
        outline_selection: list[str] | None = None,
        outline_plan: dict | None = None,
    ):
        splitter = MarkdownSplitter()
        if preflight and not force and outline_selection is None and outline_plan is None:
            return BookService.build_import_outline_confirmation(filename, content)

        chunks = splitter.split_text(
            content,
            selected_heading_ids=outline_selection,
            outline_plan=outline_plan,
        )
        for chunk in chunks:
            chunk["content_type"] = BookService.classify_chapter_content_type(
                chunk.get("title") or "",
                chunk.get("content") or "",
            )

        hard_block = BookService.run_import_hard_block(chunks)
        if hard_block:
            hard_block["chapters"] = BookService.build_import_chapter_preview(chunks)
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Import blocked by preflight.",
                    "preflight": hard_block,
                },
            )

        if preflight:
            preflight_result = await BookService.run_import_preflight(chunks)
            if preflight_result["severity"] == "blocked":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Import blocked by preflight.",
                        "preflight": preflight_result,
                    },
                )
            if preflight_result["severity"] == "warning" and not force:
                return {
                    "requires_confirmation": True,
                    "confirmation_type": "preflight",
                    "preflight": preflight_result,
                }

        book_uuid = str(uuid.uuid4())
        book_dir = BookStorage.ensure_book_dirs(book_uuid)

        safe_filename = BookStorage.sanitize_uploaded_filename(filename)
        dest_path = BookStorage._safe_book_subpath(book_uuid, safe_filename)
        dest_path.write_text(content, encoding="utf-8")

        if source_dir:
            images_source = Path(source_dir) / "images"
            if images_source.exists() and images_source.is_dir():
                shutil.copytree(images_source, book_dir / "images", dirs_exist_ok=True)

        new_book = Book(
            uuid=book_uuid,
            title=Path(safe_filename).stem,
            original_filename=safe_filename,
            status=BookStatus.loaded,
        )
        db.add(new_book)
        await db.commit()
        await db.refresh(new_book)
        
        new_chapters = []
        for idx, chunk in enumerate(chunks):
            chapter_path = BookStorage.raw_chapter_path(book_uuid, chunk["chapter_index"])
            chapter_path.write_text(chunk["content"], encoding="utf-8")

            ch = Chapter(
                book_id=new_book.id,
                chapter_index=chunk["chapter_index"],
                title_en=chunk["title"],
                content_type=chunk.get("content_type") or "main_text",
                order=idx,
            )
            db.add(ch)
            new_chapters.append(ch)
        
        await db.commit()
        plan = await BookService.build_translation_plan(new_book, new_chapters)
        new_book.translation_total = plan.total
        new_book.translation_completed = plan.completed
        new_book.translation_failed = plan.failed
        await db.commit()
        await BookService.save_meta_json(book_dir, new_book, new_chapters)
        return {"message": "Book imported successfully", "book_id": new_book.id, "total_chapters": len(chunks)}
