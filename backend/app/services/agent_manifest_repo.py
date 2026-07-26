import json
from typing import Any

import aiofiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import Chapter
from app.services.book_storage import BookStorage


class AgentManifestRepo:
    @staticmethod
    def build_initial_manifest(book_uuid: str, title: str) -> dict[str, Any]:
        return {
            "uuid": book_uuid,
            "title": title,
            "type": "generated",
            "stage": "init",
            "vision": {},
            "tree": {"id": "root", "title": title, "children": []},
        }

    @staticmethod
    async def load_manifest(book_uuid: str) -> dict[str, Any]:
        manifest_path = BookStorage.manifest_path(book_uuid)
        async with aiofiles.open(manifest_path, "r", encoding="utf-8") as handle:
            return json.loads(await handle.read())

    @staticmethod
    async def save_manifest(book_uuid: str, manifest: dict[str, Any]) -> None:
        BookStorage.ensure_book_dirs(book_uuid)
        manifest_path = BookStorage.manifest_path(book_uuid)
        async with aiofiles.open(manifest_path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(manifest, indent=2, ensure_ascii=False))

    @staticmethod
    def validate_tree_structure(tree_data: Any) -> dict[str, Any]:
        if not isinstance(tree_data, dict):
            return {"id": "root", "title": "Error", "children": []}

        def clean_node(node: Any) -> dict[str, Any] | None:
            if not isinstance(node, dict):
                return None

            cleaned = dict(node)
            if "id" not in cleaned:
                cleaned["id"] = "0"
            if "title" not in cleaned:
                cleaned["title"] = "Untitled"

            children = cleaned.get("children")
            if children is None:
                return cleaned
            if not isinstance(children, list):
                cleaned["children"] = []
                return cleaned

            valid_children = []
            for child in children:
                cleaned_child = clean_node(child)
                if cleaned_child is not None:
                    valid_children.append(cleaned_child)
            cleaned["children"] = valid_children
            return cleaned

        return clean_node(tree_data) or {"id": "root", "title": "Root", "children": []}

    @staticmethod
    def normalize_tree(title: str, tree_data: Any) -> dict[str, Any]:
        if isinstance(tree_data, list):
            validated_children = AgentManifestRepo.validate_tree_structure({"children": tree_data})["children"]
            return {"id": "root", "title": title, "children": validated_children}
        return AgentManifestRepo.validate_tree_structure(tree_data)

    @staticmethod
    def generate_preview_md(manifest: dict[str, Any]) -> str:
        md = "#### Foundational Vision\n"
        vision = manifest.get("vision", {})
        for key, value in vision.items():
            md += f"- **{key}**: {value}\n"

        md += "\n#### Table of Contents\n"

        def walk(nodes: list[dict[str, Any]], depth: int = 0) -> str:
            result = ""
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                result += "  " * depth + f"- {node.get('id', '')} {node.get('title', 'Untitled')}\n"
                children = node.get("children")
                if isinstance(children, list):
                    result += walk(children, depth + 1)
            return result

        root = manifest.get("tree", {})
        md += walk(root.get("children", []))
        return md

    @staticmethod
    def collect_file_nodes(tree: dict[str, Any]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []

        def walk(items: list[dict[str, Any]]) -> None:
            for node in items:
                if not isinstance(node, dict):
                    continue
                if node.get("type") == "file":
                    nodes.append(node)
                children = node.get("children")
                if isinstance(children, list):
                    walk(children)

        children = tree.get("children", []) if isinstance(tree, dict) else []
        if isinstance(children, list):
            walk(children)
        return nodes

    @staticmethod
    def find_node(tree: dict[str, Any], node_id: str) -> dict[str, Any] | None:
        def walk(items: list[dict[str, Any]]) -> dict[str, Any] | None:
            for node in items:
                if not isinstance(node, dict):
                    continue
                if node.get("id") == node_id:
                    return node
                children = node.get("children")
                if isinstance(children, list):
                    found = walk(children)
                    if found is not None:
                        return found
            return None

        children = tree.get("children", []) if isinstance(tree, dict) else []
        if not isinstance(children, list):
            return None
        return walk(children)

    @staticmethod
    async def sync_manifest_to_db(book, manifest: dict[str, Any], db: AsyncSession) -> list[Chapter]:
        tree = AgentManifestRepo.normalize_tree(book.title if hasattr(book, "title") else "Book", manifest.get("tree", {}))
        file_nodes = AgentManifestRepo.collect_file_nodes(tree)

        result = await db.execute(
            select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.order, Chapter.id)
        )
        existing_chapters = list(result.scalars().all())
        existing_by_index = {chapter.chapter_index: chapter for chapter in existing_chapters}
        synced: list[Chapter] = []

        for order, node in enumerate(file_nodes):
            chapter_index = str(node.get("id", "")).strip()
            if not chapter_index:
                continue

            chapter = existing_by_index.pop(chapter_index, None)
            if chapter is None:
                chapter = Chapter(
                    book_id=book.id,
                    chapter_index=chapter_index,
                    title_en=node.get("title", "Untitled"),
                    order=order,
                )
                db.add(chapter)
            else:
                chapter.title_en = node.get("title", "Untitled")
                chapter.order = order
            synced.append(chapter)

        for chapter in existing_by_index.values():
            await db.delete(chapter)

        manifest["tree"] = tree
        return synced
