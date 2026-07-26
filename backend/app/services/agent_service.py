import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_llm_adapter import AgentLLMAdapter
from app.services.agent_manifest_repo import AgentManifestRepo
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.agent_writer_runner import AgentWriterRunner


class AgentService:
    @staticmethod
    async def _load_skill(name: str) -> str:
        return await AgentLLMAdapter.load_skill(name)

    @staticmethod
    async def _ask_agent(system_prompt: str, user_prompt: str):
        return await AgentLLMAdapter.ask_agent(system_prompt, user_prompt)

    @staticmethod
    def _extract_json(text: str) -> dict:
        return AgentLLMAdapter.extract_json(text)

    @staticmethod
    def _validate_tree_structure(tree_data: dict) -> dict:
        return AgentManifestRepo.validate_tree_structure(tree_data)

    @staticmethod
    def _generate_preview_md(manifest: dict) -> str:
        return AgentManifestRepo.generate_preview_md(manifest)

    @staticmethod
    async def handle_interaction(book_id: int, message: str, db: AsyncSession, background_tasks=None):
        return await AgentOrchestrator.handle_interaction(book_id, message, db, background_tasks)

    @staticmethod
    async def architect_book_structure(book_id: int, db: AsyncSession = None):
        return await AgentOrchestrator.architect_book_structure(book_id, db)

    @staticmethod
    async def refine_structure(book_id: int, user_command: str, db: AsyncSession = None):
        return await AgentOrchestrator.refine_structure(book_id, user_command, db)

    @staticmethod
    async def initialize_agent_book(title: str, db: AsyncSession):
        return await AgentOrchestrator.initialize_agent_book(title, db)

    @staticmethod
    async def confirm_structure(book_id: int, manifest: dict, db: AsyncSession, background_tasks=None):
        return await AgentOrchestrator.confirm_structure(book_id, manifest, db, background_tasks)

    @staticmethod
    async def run_recursive_deep_dive(book_id: int, db: AsyncSession = None):
        return await AgentOrchestrator.run_recursive_deep_dive(book_id, db)

    @staticmethod
    def get_node_path(book_uuid: str, node_id: str, title: str):
        return str(AgentWriterRunner.get_node_path(book_uuid, node_id, title))

    @staticmethod
    async def write_node_content(book_uuid: str, node_id: str, title: str, content: str):
        return await AgentWriterRunner.write_node_content(book_uuid, node_id, title, content)

    @staticmethod
    async def _get_agent_context(book_uuid: str, current_node_id: str = None) -> str:
        return await AgentWriterRunner.get_agent_context(book_uuid, current_node_id)

    @staticmethod
    async def regenerate_node(book_id: int, node_id: str, instruction: str, db: AsyncSession = None):
        return await AgentOrchestrator.regenerate_node(book_id, node_id, instruction, db)

    @staticmethod
    async def sync_manifest_to_db(book, manifest: dict, db: AsyncSession):
        return await AgentManifestRepo.sync_manifest_to_db(book, manifest, db)
