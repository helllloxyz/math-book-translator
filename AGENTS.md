# Repository Guidelines

## Project Shape

Math Book Translator is a full-stack reader-first app for imported Markdown mathematics books. The main flow is:

1. Import Markdown book content.
2. Split content into chapter files.
3. Translate chapters through an LLM while preserving math markup.
4. Generate concise top-down reading guides directly from chapter bodies.
5. Read, ask questions, create notes, and inspect generated guides in the Vue reader.

The repo also contains the DeepTree Author agent workflow for generated mathematics books.

## Run And Verify

- Use the repository's Node 22 runtime through mise for all Node-dependent commands: `mise exec node@22 -- <command>`.
- Full local app: `./install.sh`, then `cp backend/.env.example backend/.env`, then `mise exec node@22 -- ./run.sh`.
- Backend only: `cd backend && source .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload`.
- Frontend only: `cd frontend && mise exec node@22 -- npm run dev`.
- Backend tests: `cd backend && source .venv/bin/activate && pytest`.
- Frontend build: `cd frontend && mise exec node@22 -- npm run build`.
- Frontend tests are plain Node scripts: run individual `*.test.mjs` files through mise, for example `cd frontend && mise exec node@22 -- node src/utils/readerTree.test.mjs`.

`run.sh` applies Alembic migrations by default. Use `RUN_DB_MIGRATIONS=0 ./run.sh` to skip, or `DB_MIGRATION_MODE=check ./run.sh` to make app startup verify the database revision.

Do not commit local runtime artifacts: `.env`, `*.db`, logs, `storage/`, `backend/storage/`, `.superpowers/`, `.worktrees/`, `frontend/dist/`, and virtual environments.

## Code Architecture Map

### Backend Entry And Boundaries

- `backend/app/main.py` creates the FastAPI app, loads settings at startup, optionally checks Alembic state, mounts `/static` to `BookStorage.static_dir()`, mounts `/config`, configures CORS, and includes all routers.
- `backend/app/models/base.py` owns async SQLAlchemy engine/session setup from `DATABASE_URL`.
- `backend/app/models/schema.py` defines SQLAlchemy models and request schemas:
  - `Book`: imported or generated book metadata, status, progress, agent state, optional vision JSON.
  - `Chapter`: chapter index/title/order linked to a book; content lives on disk.
  - `UserNote`: reader notes, chat notes, quiz/selection/chapter note records.
  - enums: `BookStatus`, `AgentStage`, `BookType`, `NoteType`.
- `backend/alembic/` contains schema migrations. Prefer migrations over ad hoc database mutations.

### Backend Routers

- `backend/app/routers/books.py`: list/import/upload/read/rename/delete books, reader tree, and translation trigger.
- `backend/app/routers/chapters.py`: source/translated chapter content.
- `backend/app/routers/chat.py`: one-shot ask endpoint and streaming chat endpoint.
- `backend/app/routers/guides.py`: list/read/generate top-down guides.
- `backend/app/routers/settings.py`: persisted LLM/storage/provider settings.
- `backend/app/routers/legacy.py`: notes APIs plus DeepTree Author agent endpoints kept for compatibility.

Keep routers thin: request validation, dependency wiring, HTTP errors, and delegation to services.

### Backend Services

- `backend/app/services/book_storage.py`: canonical filesystem boundary. Use it for storage root, book directories, source chapter paths, translated chapter paths, guide paths, manifest paths, and safe filename handling.
- `backend/app/services/parser.py`: `MarkdownSplitter` turns imported Markdown into chapter chunks.
- `backend/app/services/book_service.py`: import, upload normalization, chapter file creation, translation planning/progress, background translation, and guide generation orchestration.
- `backend/app/services/translator.py`: single LLM adapter boundary. It selects OpenAI-compatible, Gemini, or Anthropic clients from settings/env and provides `complete()`, translation, one-shot ask, and streaming chat helpers.
- `backend/app/services/chapter_source_service.py`: complete direct chapter-body loading for Guide and Quiz prompts; import preflight owns the chapter-length boundary.
- `backend/app/services/guide_compiler_service.py`: book-level top-down guide prompt, guide JSON normalization, filename/source-id construction, guide markdown writes, and guide manifest writes.
- `backend/app/services/guide_service.py`: facade for listing, reading, and generating guides.
- `backend/app/services/reader_tree_service.py`: builds reader navigation trees from chapters and generated guides.
- `backend/app/services/settings_service.py`: reads/writes provider and storage settings.
- `backend/app/services/llm_json.py`: robust JSON extraction from LLM output.
- `backend/app/services/agent_service.py`, `agent_orchestrator.py`, `agent_writer_runner.py`, `agent_manifest_repo.py`, `agent_llm_adapter.py`, `interaction_service.py`: DeepTree Author book generation, manifest storage, LLM skill execution, and trajectory logging.

### Frontend Entry And State

- `frontend/src/main.js`: Vue app bootstrap, Pinia, router, global CSS.
- `frontend/src/router/index.js`: routes for library, reader, notes, and standalone conversation page.
- `frontend/src/api/client.js`: Axios client and API URL construction. Default backend is `http://localhost:8000`, override with `VITE_API_URL`.
- `frontend/src/stores/bookStore.js`: Pinia store for books, imports/uploads, translation, chapter content, notes, reader tree, and guides.

### Frontend Views

- `frontend/src/views/Library.vue`: book list, import/upload, preferences, translation progress, rename/delete, and package import/export.
- `frontend/src/views/Reader.vue`: main reading workspace. It coordinates book/guide tree navigation, source/translation rendering, notes/cards, selection chat, quiz, and source highlighting.
- `frontend/src/views/Notes.vue`: book note list and note chat interactions.
- `frontend/src/views/ConversationPage.vue`: full-page conversation view backed by local conversation payload metadata.

### Frontend Components And Composables

- Reader shell: `Sidebar.vue`, `ReaderTreeNode.vue`, `ReaderPanes.vue`, `ReaderToolbar.vue`, `ContextMenu.vue`.
- Notes/conversation: `NotesPanel.vue`, `NoteCard.vue`, `LearningSidebar.vue`, `ConversationCard.vue`, `ConversationDialog.vue`, `QuizCard.vue`.
- Library/settings: `ImportModal.vue`, `SettingsModal.vue`, `MacroSettingsModal.vue`.
- `frontend/src/composables/useReaderContent.js`: fetch/render selected chapter or guide content, trigger KaTeX/Mermaid rendering, and manage rendered HTML.
- `frontend/src/composables/useLearningCards.js`: local note/card creation and serialization.
- `frontend/src/composables/useChat.js`: streaming chat wrappers.
- `frontend/src/composables/useSelectionMenu.js`: text selection context menu behavior.
- `frontend/src/utils/renderer.js`: Markdown-It, KaTeX, Mermaid, image URL rewriting, math rendering.
- `frontend/src/utils/readerTree.js`: flatten/find/adjacent reader tree helpers.
- `frontend/src/utils/chatMessages.js` and `conversationMetadata.js`: note conversation serialization and local metadata.

## Runtime Data Layout

`BookStorage` resolves `STORAGE_DIR` from the environment/settings and creates one directory per book UUID:

- `book_md/`: source chapter Markdown files.
- `book_trans_md/`: translated Chinese chapter Markdown files.
- `book_guides/`: generated guide Markdown plus `guides.json`.
- `images/`: copied imported image assets when available.
- `meta.json` / `00_meta.json`: book or agent metadata, depending on workflow.
- `history.jsonl`: DeepTree Author trajectory log.

When adding code that touches files, call `BookStorage` helpers instead of constructing paths inline.

## Main Data Flows

### Import

`books` router -> `BookService.handle_book_import()` or `create_book_from_content()` -> `MarkdownSplitter` -> `Book` and `Chapter` rows -> source chapter files under `book_md/`.

### Translation

`POST /books/{id}/translate` -> background `BookService.process_book_translation()` -> `TranslatorService.translate_text()` -> translated files under `book_trans_md/`.

### Guide Generation

Completed translation -> `BookService.generate_guides_for_translated_book()` -> direct body loading through `ChapterSourceService` -> `GuideCompilerService.generate_top_down_guides()` -> guide markdown and `book_guides/guides.json`.

### Reader

`Reader.vue` -> `bookStore.fetchReaderTree()` and `useReaderContent()` -> chapter content from `/chapters/{id}/content` or guide content from `/books/{id}/guides/{filename}` -> `renderer.js` for Markdown/KaTeX/Mermaid.

### Chat And Notes

Selection/chapter chat UI -> `useChat.js` streaming endpoints -> `TranslatorService.stream_messages()`. Structured Quiz uses `/chapters/{id}/quiz/next` for a Feynman-style question and `/quiz/questions/{id}/attempts` for history-aware semantic evaluation. Conversation records are persisted through legacy note endpoints and stored in `UserNote`.

### DeepTree Author

The frontend authoring console has been retired. Legacy `/agent/*` routes still delegate to agent services and skills in `backend/app/skills/`, with manifests/content/history stored in the book storage directory.

## Engineering Conventions

- Keep HTTP contract changes in routers and workflow changes in services.
- Treat `TranslatorService` as the only provider SDK boundary.
- Treat `BookStorage` as the only filesystem layout boundary.
- Preserve KaTeX-compatible math delimiters in generated or translated Markdown.
- Keep Pydantic/SQLAlchemy schema changes paired with Alembic migrations and tests.
- For frontend changes, prefer existing Composition API patterns and Pinia store actions over introducing new global state.
- For reader behavior, update both the relevant composable/component and the focused `*.test.mjs` file when possible.

## Known Sharp Edges

- `backend/.env` may contain real local credentials; never print or copy secret values into committed docs or logs.
- Older imported packages can still contain a legacy `book_learning/` directory. Runtime code ignores it and new exports omit it.
