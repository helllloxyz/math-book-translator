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
- `chapters` router: source and translated chapter content.
- `chat` router: ask and streaming chat endpoints.
- `guides` router: list/read/generate top-down guides.
- `legacy` router: backward-compatible note APIs and legacy endpoints.

Routers should stay thin: validation, dependency injection, and handoff to services.

## BookStorage Boundary

`backend/app/services/book_storage.py` is the canonical path boundary. It owns:

- storage root resolution (`STORAGE_DIR`).
- per-book directory layout (`book_md`, `book_trans_md`, `book_guides`, `book_user`).
- safe file naming for chapter indexes and guide slugs.

Other modules should call `BookStorage` helpers instead of building storage paths inline.

## ChapterSource Boundary

`backend/app/services/chapter_source_service.py` keeps the chapter body as the only factual source:

- prefers the translated body and falls back to the original body.
- returns the complete imported chapter body without a second context-length limit.
- never calls an LLM and never persists a derived chapter summary.

## GuideCompiler Boundary

`backend/app/services/guide_compiler_service.py` owns top-down guide compilation:

- builds chapter guides directly from complete chapter bodies.
- rolls child guide summaries into directory and book guides.
- validates/parses guide JSON output.
- checkpoints guide markdown and manifest entries under `book_guides/`.

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
3. Top-down guide generation reads chapter bodies directly and writes concise guides.
4. Reader loads chapter content or generated guides; a missing guide remains an explicit empty state.
5. Selection chat uses selected text; chapter chat and Quiz use complete chapter bodies. Quiz has explicit `chapter` and `book` modes and uses type-specific Feynman teach-back prompts rather than formula-entry exercises.
