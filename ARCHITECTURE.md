# Math Book Translator Architecture

This document describes the current architecture for the import -> translation -> reader -> structured learning pipeline.

## System Boundaries

The backend is organized around API routers and focused services:

- Routers define HTTP contracts and request/response wiring.
- Domain services implement workflow logic.
- `BookStorage` is the filesystem boundary for book artifacts.
- `TranslatorService` is the LLM boundary.

## Router Layer

`backend/app/main.py` composes routers:

- `settings` router: model/provider/storage configuration.
- `books` router: book import, list, detail, delete, translation trigger.
- `chapters` router: chapter content and chapter learning context.
- `chat` router: ask and streaming chat endpoints.
- `guides` router: list/read/generate top-down guides.
- `legacy` router: backward-compatible note APIs and legacy endpoints.

Routers should stay thin: validation, dependency injection, and handoff to services.

## BookStorage Boundary

`backend/app/services/book_storage.py` is the canonical path boundary. It owns:

- storage root resolution (`STORAGE_DIR`).
- per-book directory layout (`book_md`, `book_trans_md`, `book_learning`, `book_guides`).
- safe file naming for chapter indexes and guide slugs.

Other modules should call `BookStorage` helpers instead of building storage paths inline.

## LearningContext Boundary

`backend/app/services/learning_context_service.py` owns chapter learning context lifecycle:

- schema defaults and normalization.
- chapter learning compile prompt construction.
- JSON extraction/validation of LLM output.
- read/write of `book_learning/*_learning.json`.
- low-token chat context formatting for reader interactions.

`BookService.process_book_translation` compiles learning context after each translated chapter write.

## GuideCompiler Boundary

`backend/app/services/guide_compiler_service.py` owns top-down guide compilation:

- builds book-level prompt from chapter learning contexts.
- validates/parses guide JSON output.
- writes guide markdown files under `book_guides/`.

`GuideService` is a thin facade for listing, reading, and delegating guide generation.

## LLM Service Boundary

`backend/app/services/translator.py` is the single LLM adapter boundary:

- provider selection via settings (`openai` compatible, Gemini, Anthropic).
- shared `complete()` path for service-to-LLM calls.
- translation and reader chat helpers.
- streaming chat support.

Services requiring model output should call `TranslatorService` rather than provider SDKs directly.

## End-to-End Runtime Flow

1. `books` router imports Markdown and stores chapter source files.
2. Translation background task writes translated chapter files.
3. Learning context compilation runs per chapter and persists structured JSON.
4. Reader loads chapter content and chapter learning context.
5. Chat requests use compact learning-context-based prompts.
6. Top-down guide generation compiles book-level guide markdown from chapter contexts.
