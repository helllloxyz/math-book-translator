from pathlib import Path
import json

import aiofiles

from app.services.book_storage import BookStorage
from app.services.guide_compiler_service import GuideCompilerService


class GuideService:
    @staticmethod
    def get_guide_dir(book_uuid: str) -> Path:
        return BookStorage.guide_dir(book_uuid)

    @staticmethod
    async def list_guides(book_uuid: str) -> list[dict[str, str]]:
        guide_dir = GuideService.get_guide_dir(book_uuid)
        if not guide_dir.is_dir():
            return []

        manifest_path = BookStorage.guide_manifest_path(book_uuid)
        if manifest_path.exists():
            async with aiofiles.open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.loads(await handle.read())
            guides = []
            for guide in manifest if isinstance(manifest, list) else []:
                if not isinstance(guide, dict):
                    continue
                filename = str(guide.get("filename") or "")
                if not filename or not (guide_dir / filename).exists():
                    continue
                title = str(guide.get("title") or Path(filename).stem)
                guides.append(
                    {
                        "id": str(guide.get("id") or f"guide:{filename}"),
                        "filename": filename,
                        "title": title,
                        "scope_type": str(guide.get("scope_type") or "book"),
                        "scope_id": str(guide.get("scope_id") or "book"),
                        "source_type": str(guide.get("source_type") or "book_guide"),
                        "source_id": str(guide.get("source_id") or f"guide:{filename}"),
                        "source_title": str(guide.get("source_title") or title),
                    }
                )
            return guides

        guides = []
        for path in sorted(guide_dir.glob("*.md")):
            async with aiofiles.open(path, "r", encoding="utf-8") as handle:
                first_line = (await handle.readline()).strip()
            title = first_line.lstrip("#").strip() or path.stem
            guides.append(
                {
                    "id": f"guide:{path.name}",
                    "filename": path.name,
                    "title": title,
                    "scope_type": "book",
                    "scope_id": "book",
                    "source_type": "book_guide",
                    "source_id": f"guide:book:{path.stem}",
                    "source_title": title,
                }
            )
        return guides

    @staticmethod
    def validate_guide_filename(filename: str) -> str:
        if "/" in filename or "\\" in filename or not filename.endswith(".md"):
            raise ValueError("Invalid guide filename")
        return filename

    @staticmethod
    async def read_guide(book_uuid: str, filename: str) -> dict[str, str]:
        safe_filename = GuideService.validate_guide_filename(filename)
        path = BookStorage.guide_dir(book_uuid) / safe_filename
        if not path.exists():
            raise FileNotFoundError("Guide not found")

        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            return {"content": await handle.read()}

    @staticmethod
    async def generate_top_down_guides(book, chapters, translator) -> list[dict[str, str]]:
        return await GuideCompilerService.generate_top_down_guides(book, chapters, translator)

    @staticmethod
    async def generate_chapter_guide(book, chapter, translator) -> list[dict[str, str]]:
        return await GuideCompilerService.generate_chapter_guide(book, chapter, translator)
