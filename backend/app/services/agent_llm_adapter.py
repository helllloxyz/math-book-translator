from pathlib import Path
from typing import Any

import aiofiles

from app.services.llm_json import extract_json_candidate
from app.services.translator import TranslatorService


class AgentLLMAdapter:
    @staticmethod
    async def load_skill(name: str) -> str:
        skill_path = Path(__file__).resolve().parent.parent / "skills" / f"{name}.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_path}")
        async with aiofiles.open(skill_path, "r", encoding="utf-8") as handle:
            return await handle.read()

    @staticmethod
    async def ask_agent(system_prompt: str, user_prompt: str) -> str:
        translator = TranslatorService(task="agent")
        return await translator.complete(user_prompt, system_prompt, temperature=0.3)

    @staticmethod
    def extract_json(text: str) -> dict[str, Any]:
        parsed = extract_json_candidate(text, validator=lambda data: isinstance(data, dict))
        return dict(parsed)


AgentLlmAdapter = AgentLLMAdapter
