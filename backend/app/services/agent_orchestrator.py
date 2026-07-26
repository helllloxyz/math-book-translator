import asyncio
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import SessionLocal
from app.models.schema import AgentStage, Book, BookStatus, BookType
from app.services.agent_llm_adapter import AgentLLMAdapter
from app.services.agent_manifest_repo import AgentManifestRepo
from app.services.agent_writer_runner import AgentWriterRunner
from app.services.book_storage import BookStorage
from app.services.interaction_service import InteractionEntry, InteractionService

logger = logging.getLogger("app.agent_service")


class AgentOrchestrator:
    @staticmethod
    async def _get_book(book_id: int, db: AsyncSession) -> Book | None:
        result = await db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def handle_interaction(book_id: int, message: str, db: AsyncSession, background_tasks=None):
        book = await AgentOrchestrator._get_book(book_id, db)
        if not book:
            return {"status": "error", "message": "Book not found"}

        manifest = await AgentManifestRepo.load_manifest(book.uuid)
        msg = message.strip()
        msg_lower = msg.lower()

        if msg_lower == "help":
            help_text = (
                "### Available Commands\n\n"
                "- `build`: Start the initial architecting phase (only in 'init' stage).\n"
                "- `confirm` / `yes`: Finalize the TOC and start writing content.\n"
                "- Any other text: Describe changes you want to the current blueprint.\n"
                "- `help`: Show this message."
            )
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="console",
                    command="help",
                    response=help_text,
                    status="success",
                ),
            )
            return {"status": "success", "message": "Help displayed in console."}

        if msg_lower == "build" and book.agent_stage == AgentStage.init:
            if background_tasks:
                background_tasks.add_task(AgentOrchestrator.architect_book_structure, book_id, None)
            return {"status": "success", "message": "Architecting the entire math landscape... Please wait."}

        if msg_lower in {"yes", "confirm"} and book.agent_stage == AgentStage.reviewing:
            await AgentOrchestrator.confirm_structure(book_id, manifest, db, background_tasks)
            return {"status": "success", "message": "Structure confirmed. Starting deep dive generation."}

        if book.agent_stage == AgentStage.reviewing:
            if background_tasks:
                background_tasks.add_task(AgentOrchestrator.refine_structure, book_id, message, None)
            return {"status": "success", "message": "Analyzing your requests and updating the blueprint..."}

        return {
            "status": "error",
            "message": f"Invalid command for stage {book.agent_stage.value}. Type 'help' for options.",
        }

    @staticmethod
    async def architect_book_structure(book_id: int, db: AsyncSession = None):
        if db is None:
            async with SessionLocal() as session:
                await AgentOrchestrator.architect_book_structure(book_id, session)
                return

        book = await AgentOrchestrator._get_book(book_id, db)
        if not book:
            return

        await InteractionService.log_interaction(
            book.uuid,
            InteractionEntry(
                timestamp=datetime.utcnow().isoformat(),
                node="root",
                command="Architecting",
                response="[Trace] Loading Architect skill and preparing domain vision...",
                status="info",
            ),
        )

        try:
            skill_tpl = await AgentLLMAdapter.load_skill("architect")
            user_prompt = f"Design a book for {book.title}"
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="Architecting",
                    response=f"[Trace] Calling LLM with prompt:\n\n```text\n{user_prompt}\n```",
                    status="info",
                ),
            )
            response = await AgentLLMAdapter.ask_agent(skill_tpl.format(domain=book.title), user_prompt)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="Architecting",
                    response="[Trace] LLM responded. Parsing mathematical blueprint...",
                    status="info",
                ),
            )
            raw_data = AgentLLMAdapter.extract_json(response)
            manifest = await AgentManifestRepo.load_manifest(book.uuid)
            manifest["vision"] = raw_data.get("vision", {})
            manifest["tree"] = AgentManifestRepo.normalize_tree(book.title, raw_data.get("tree", []))
            manifest["stage"] = AgentStage.reviewing.value
            await AgentManifestRepo.save_manifest(book.uuid, manifest)

            book.agent_stage = AgentStage.reviewing
            book.vision = manifest["vision"]
            await db.commit()

            preview = AgentManifestRepo.generate_preview_md(manifest)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="architect",
                    response=(
                        "### Mathematics Blueprint Ready\n\n"
                        f"{preview}\n\n"
                        "**Type any changes you want, or 'confirm' to start writing.**"
                    ),
                    status="success",
                ),
            )
        except Exception as exc:
            logger.error("Architecting failed for book %s: %s", book_id, exc, exc_info=True)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="architect",
                    response=(
                        "### ❌ Architecting Failed\n\n"
                        f"Error: {exc}\n\n"
                        "Please try again by typing `build`."
                    ),
                    status="error",
                ),
            )

    @staticmethod
    async def refine_structure(book_id: int, user_command: str, db: AsyncSession = None):
        if db is None:
            async with SessionLocal() as session:
                await AgentOrchestrator.refine_structure(book_id, user_command, session)
                return

        book = await AgentOrchestrator._get_book(book_id, db)
        if not book:
            return

        try:
            manifest = await AgentManifestRepo.load_manifest(book.uuid)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="Refining",
                    response=(
                        f"[Trace] Loading Refiner skill and analyzing blueprint for command: '{user_command}'..."
                    ),
                    status="info",
                ),
            )
            skill_tpl = await AgentLLMAdapter.load_skill("refiner")
            sys_prompt = skill_tpl.format(
                domain=book.title,
                current_manifest=json.dumps(manifest, indent=2),
                user_command=user_command,
            )
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="Refining",
                    response=f"[Trace] Calling LLM with refinement instructions:\n\n> {user_command}",
                    status="info",
                ),
            )
            response = await AgentLLMAdapter.ask_agent(sys_prompt, user_command)
            data = AgentLLMAdapter.extract_json(response)

            manifest["vision"] = data.get("vision", manifest.get("vision", {}))
            if "tree" in data:
                updated_tree = data["tree"]
                if isinstance(updated_tree, list):
                    manifest.setdefault("tree", {"id": "root", "title": book.title, "children": []})
                    manifest["tree"]["children"] = AgentManifestRepo.normalize_tree(book.title, updated_tree)["children"]
                else:
                    manifest["tree"] = AgentManifestRepo.normalize_tree(book.title, updated_tree)
            await AgentManifestRepo.save_manifest(book.uuid, manifest)

            book.vision = manifest.get("vision", {})
            await db.commit()

            preview = AgentManifestRepo.generate_preview_md(manifest)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="refine",
                    response=(
                        "### Blueprint Updated\n\n"
                        f"{preview}\n\n"
                        "**Any more changes? Or type 'confirm' to proceed.**"
                    ),
                    status="success",
                ),
            )
        except Exception as exc:
            logger.error("Refinement failed for book %s: %s", book_id, exc, exc_info=True)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="refine",
                    response=(
                        "### ❌ Refinement Failed\n\n"
                        f"Error: {exc}\n\n"
                        "Please try rephrasing your request."
                    ),
                    status="error",
                ),
            )

    @staticmethod
    async def initialize_agent_book(title: str, db: AsyncSession):
        book_uuid = str(uuid.uuid4())
        BookStorage.ensure_book_dirs(book_uuid)
        manifest = AgentManifestRepo.build_initial_manifest(book_uuid, title)
        await AgentManifestRepo.save_manifest(book_uuid, manifest)

        new_book = Book(
            uuid=book_uuid,
            title=title,
            original_filename=f"{title}.agent",
            status=BookStatus.loaded,
            type=BookType.generated,
            agent_stage=AgentStage.init,
            vision={},
        )
        db.add(new_book)
        await db.commit()
        await db.refresh(new_book)

        await InteractionService.log_interaction(
            book_uuid,
            InteractionEntry(
                timestamp=datetime.utcnow().isoformat(),
                node="system",
                command="init",
                response=(
                    f"### Book Initialized: {title}\n\n"
                    "Mathematical domain established. Type `build` to begin architecting the landscape."
                ),
                status="success",
            ),
        )
        return new_book

    @staticmethod
    async def confirm_structure(book_id: int, manifest: dict, db: AsyncSession, background_tasks=None):
        book = await AgentOrchestrator._get_book(book_id, db)
        if not book:
            return

        current_manifest = await AgentManifestRepo.load_manifest(book.uuid)
        merged_manifest = dict(current_manifest)
        merged_manifest.update(manifest or {})
        merged_manifest["uuid"] = book.uuid
        merged_manifest["title"] = current_manifest.get("title") or book.title
        merged_manifest["vision"] = merged_manifest.get("vision", {})
        merged_manifest["tree"] = AgentManifestRepo.normalize_tree(book.title, merged_manifest.get("tree", {}))
        merged_manifest["stage"] = AgentStage.confirmed.value

        await AgentManifestRepo.sync_manifest_to_db(book, merged_manifest, db)
        await AgentManifestRepo.save_manifest(book.uuid, merged_manifest)

        book.agent_stage = AgentStage.confirmed
        book.vision = merged_manifest.get("vision", {})
        await db.commit()

        if background_tasks:
            background_tasks.add_task(AgentOrchestrator.run_recursive_deep_dive, book_id, None)
        else:
            await AgentOrchestrator.run_recursive_deep_dive(book_id, db)

    @staticmethod
    async def run_recursive_deep_dive(book_id: int, db: AsyncSession = None):
        if db is None:
            async with SessionLocal() as session:
                await AgentOrchestrator.run_recursive_deep_dive(book_id, session)
                return

        book = await AgentOrchestrator._get_book(book_id, db)
        if not book:
            return

        manifest = await AgentManifestRepo.load_manifest(book.uuid)
        manifest["stage"] = AgentStage.writing.value
        await AgentManifestRepo.save_manifest(book.uuid, manifest)

        book.agent_stage = AgentStage.writing
        book.status = BookStatus.generating
        await db.commit()

        try:
            vision_ctx = json.dumps(manifest.get("vision", {}), indent=2)
            file_nodes = AgentWriterRunner.collect_file_nodes(manifest.get("tree", {}))
            skill_tpl = await AgentLLMAdapter.load_skill("writer")
            semaphore = asyncio.Semaphore(3)

            async def generate_node_task(node: dict):
                async with semaphore:
                    path = AgentWriterRunner.get_node_path(book.uuid, node["id"], node.get("title"))
                    if path.exists():
                        return

                    await InteractionService.log_interaction(
                        book.uuid,
                        InteractionEntry(
                            timestamp=datetime.utcnow().isoformat(),
                            node=node["id"],
                            command="Writing",
                            response=f"[Trace] Starting parallel generation for {node['title']}...",
                            status="info",
                        ),
                    )
                    try:
                        history_ctx = await AgentWriterRunner.get_agent_context(book.uuid, node["id"])
                        full_ctx = f"Vision:\n{vision_ctx}\n\nRecent History:\n{history_ctx}"
                        sys_prompt = skill_tpl.format(
                            domain=book.title,
                            vision=full_ctx,
                            node_id=node["id"],
                            title=node["title"],
                        )
                        content = await AgentLLMAdapter.ask_agent(sys_prompt, f"Write section {node['id']}")
                        await AgentWriterRunner.write_node_content(book.uuid, node["id"], node["title"], content)
                        await InteractionService.log_interaction(
                            book.uuid,
                            InteractionEntry(
                                timestamp=datetime.utcnow().isoformat(),
                                node=node["id"],
                                command="Complete",
                                response=f"Finished: {node['title']}",
                                status="success",
                            ),
                        )
                    except Exception as exc:
                        logger.error("Failed node %s: %s", node["id"], exc)
                        await InteractionService.log_interaction(
                            book.uuid,
                            InteractionEntry(
                                timestamp=datetime.utcnow().isoformat(),
                                node=node["id"],
                                command="Error",
                                response=f"Failed: {exc}",
                                status="error",
                            ),
                        )

            await asyncio.gather(*(generate_node_task(node) for node in file_nodes))
            manifest["stage"] = AgentStage.ready.value
            await AgentManifestRepo.save_manifest(book.uuid, manifest)
            book.status = BookStatus.translated
            book.agent_stage = AgentStage.ready
            await db.commit()
        except Exception as exc:
            logger.error("Deep dive failed: %s", exc, exc_info=True)
            book.status = BookStatus.failed
            await db.commit()
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node="root",
                    command="DeepDive",
                    response=f"### ❌ Generation Halted\n\nError: {exc}",
                    status="error",
                ),
            )

    @staticmethod
    async def regenerate_node(book_id: int, node_id: str, instruction: str, db: AsyncSession = None):
        if db is None:
            async with SessionLocal() as session:
                await AgentOrchestrator.regenerate_node(book_id, node_id, instruction, session)
                return

        book = await AgentOrchestrator._get_book(book_id, db)
        if not book:
            return

        try:
            manifest = await AgentManifestRepo.load_manifest(book.uuid)
            node = AgentManifestRepo.find_node(manifest.get("tree", {}), node_id)
            if not node:
                return

            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node=node_id,
                    command="Regenerating",
                    response=f"Revision: {instruction}",
                    status="info",
                ),
            )

            vision_ctx = json.dumps(manifest.get("vision", {}), indent=2)
            history_ctx = await AgentWriterRunner.get_agent_context(book.uuid, node_id)
            full_ctx = (
                f"Vision:\n{vision_ctx}\n\nRecent History:\n{history_ctx}\n\n"
                f"USER SPECIFIC INSTRUCTION: {instruction}"
            )
            skill_tpl = await AgentLLMAdapter.load_skill("writer")
            sys_prompt = skill_tpl.format(
                domain=book.title,
                vision=full_ctx,
                node_id=node_id,
                title=node["title"],
            )
            content = await AgentLLMAdapter.ask_agent(
                sys_prompt,
                f"Regenerate section {node_id} with instruction: {instruction}",
            )
            await AgentWriterRunner.write_node_content(book.uuid, node_id, node["title"], content)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node=node_id,
                    command="Complete",
                    response=f"Successfully regenerated {node_id}",
                    status="success",
                ),
            )
        except Exception as exc:
            logger.error("Regeneration failed for node %s: %s", node_id, exc, exc_info=True)
            await InteractionService.log_interaction(
                book.uuid,
                InteractionEntry(
                    timestamp=datetime.utcnow().isoformat(),
                    node=node_id,
                    command="Error",
                    response=f"### ❌ Regeneration Failed\n\nError: {exc}",
                    status="error",
                ),
            )
