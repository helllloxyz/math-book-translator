from pathlib import Path
from typing import Any

import aiofiles

from app.services.book_storage import BookStorage
from app.services.interaction_service import InteractionService


class AgentWriterRunner:
    @staticmethod
    def get_node_path(book_uuid: str, node_id: str, title: str | None = None) -> Path:
        return BookStorage.agent_node_path(book_uuid, node_id)

    @staticmethod
    async def write_node_content(book_uuid: str, node_id: str, title: str, content: str) -> Path:
        path = AgentWriterRunner.get_node_path(book_uuid, node_id, title)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as handle:
            await handle.write(content)
        return path

    @staticmethod
    async def get_agent_context(book_uuid: str, current_node_id: str | None = None) -> str:
        history = await InteractionService.get_history(book_uuid)
        summaries = []
        for entry in history:
            if entry.status == "success" and entry.command == "Writing":
                summaries.append(f"Ch {entry.node}: {entry.response[:200]}")
        return "\n".join(summaries[-5:])

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
