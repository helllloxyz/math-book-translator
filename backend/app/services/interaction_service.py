import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiofiles
from pydantic import BaseModel

from app.services.book_storage import BookStorage


class InteractionEntry(BaseModel):
    timestamp: str
    node: str
    command: Optional[str] = None
    prompt: Optional[str] = None
    response: Optional[str] = None
    status: str
    metadata: Dict[str, Any] = {}


class InteractionService:
    @staticmethod
    async def log_interaction(book_uuid: str, entry: InteractionEntry):
        history_path = BookStorage.history_path(book_uuid)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(history_path, "a", encoding="utf-8") as handle:
            await handle.write(json.dumps(entry.model_dump(), ensure_ascii=False) + "\n")

    @staticmethod
    async def get_history(book_uuid: str) -> List[InteractionEntry]:
        history_path = BookStorage.history_path(book_uuid)
        if not history_path.exists():
            return []

        history = []
        async with aiofiles.open(history_path, "r", encoding="utf-8") as handle:
            async for line in handle:
                if line.strip():
                    history.append(InteractionEntry(**json.loads(line)))
        return history

    @staticmethod
    async def revoke_interaction(book_uuid: str, timestamp: str):
        entry = InteractionEntry(
            timestamp=datetime.utcnow().isoformat(),
            node="system",
            command=f"/revoke {timestamp}",
            status="revoked",
            metadata={"revoked_timestamp": timestamp},
        )
        await InteractionService.log_interaction(book_uuid, entry)
