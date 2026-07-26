import os
import re
from pathlib import Path


class BookStorage:
    _INVALID_FILENAME_CHARS = re.compile(r'[^0-9A-Za-z._\-\s]+')

    @staticmethod
    def storage_dir() -> Path:
        return Path(os.getenv("STORAGE_DIR", "storage"))

    @staticmethod
    def static_dir() -> Path:
        return BookStorage.storage_dir()

    @staticmethod
    def chapter_filename_stem(chapter_index: str) -> str:
        safe_index = str(chapter_index).replace("\\", "_").replace("/", "_")
        safe_index = safe_index.replace(".", "_")
        safe_index = safe_index.strip(" _")
        return safe_index or "chapter"

    @staticmethod
    def sanitize_chapter_index(chapter_index: str) -> str:
        safe_index = re.sub(r"[^0-9A-Za-z]+", "_", chapter_index).strip("._")
        return safe_index or "chapter"

    @staticmethod
    def sanitize_guide_slug(slug: str) -> str:
        safe_slug = "".join(ch for ch in slug if ch.isalnum() or ch in ("-", "_")).strip("-_")
        return safe_slug or "guide"

    @staticmethod
    def sanitize_uploaded_filename(filename: str) -> str:
        basename = Path(str(filename)).name.replace("\\", "/").split("/")[-1]
        safe_name = BookStorage._INVALID_FILENAME_CHARS.sub("_", basename).strip("._ ")
        if not safe_name:
            safe_name = "book.md"
        if not safe_name.lower().endswith(".md"):
            safe_name = f"{safe_name}.md"
        return safe_name

    @staticmethod
    def book_dir(book_uuid: str) -> Path:
        return BookStorage.storage_dir() / book_uuid

    @staticmethod
    def _safe_book_subpath(book_uuid: str, *parts: str) -> Path:
        base = BookStorage.book_dir(book_uuid).resolve()
        candidate = base.joinpath(*parts).resolve()
        if candidate != base and base not in candidate.parents:
            raise ValueError(f"Unsafe path resolved outside book directory: {candidate}")
        return candidate

    @staticmethod
    def manifest_path(book_uuid: str) -> Path:
        return BookStorage._safe_book_subpath(book_uuid, "00_meta.json")

    @staticmethod
    def history_path(book_uuid: str) -> Path:
        return BookStorage._safe_book_subpath(book_uuid, "history.jsonl")

    @staticmethod
    def raw_chapter_path(book_uuid: str, chapter_index: str) -> Path:
        safe_index = BookStorage.chapter_filename_stem(chapter_index)
        return BookStorage._safe_book_subpath(book_uuid, "book_md", f"{safe_index}.md")

    @staticmethod
    def agent_node_path(book_uuid: str, node_id: str) -> Path:
        return BookStorage.raw_chapter_path(book_uuid, node_id)

    @staticmethod
    def translated_chapter_path(book_uuid: str, chapter_index: str) -> Path:
        safe_index = BookStorage.chapter_filename_stem(chapter_index)
        return BookStorage._safe_book_subpath(book_uuid, "book_trans_md", f"{safe_index}_trans_zh.md")

    @staticmethod
    def learning_path(book_uuid: str, chapter_index: str) -> Path:
        safe_index = BookStorage.chapter_filename_stem(chapter_index)
        return BookStorage._safe_book_subpath(book_uuid, "book_learning", f"{safe_index}.md")

    @staticmethod
    def user_dir(book_uuid: str) -> Path:
        return BookStorage._safe_book_subpath(book_uuid, "book_user")

    @staticmethod
    def user_profile_path(book_uuid: str) -> Path:
        return BookStorage._safe_book_subpath(book_uuid, "book_user", "User.md")

    @staticmethod
    def user_profile_meta_path(book_uuid: str) -> Path:
        return BookStorage._safe_book_subpath(book_uuid, "book_user", "profile_meta.json")

    @staticmethod
    def guide_dir(book_uuid: str) -> Path:
        return BookStorage.book_dir(book_uuid) / "book_guides"

    @staticmethod
    def guide_manifest_path(book_uuid: str) -> Path:
        return BookStorage._safe_book_subpath(book_uuid, "book_guides", "guides.json")

    @staticmethod
    def guide_path(book_uuid: str, slug: str) -> Path:
        safe_slug = BookStorage.sanitize_guide_slug(slug)
        return BookStorage._safe_book_subpath(book_uuid, "book_guides", f"{safe_slug}.md")

    @staticmethod
    def ensure_book_dirs(book_uuid: str | None = None, *, root: str | Path | None = None) -> Path:
        book_root = Path(root) if root is not None else BookStorage.book_dir(book_uuid or "")
        for dirname in ("book_md", "book_trans_md", "book_learning", "book_guides", "book_user"):
            (book_root / dirname).mkdir(parents=True, exist_ok=True)
        return book_root
