# Math Book Translator

Math Book Translator is a reader-first product for imported Markdown math books.

## Product Direction

The current product focuses on five workflows:

1. Import Markdown math books from local files.
2. Translate chapters with an LLM while preserving math notation.
3. Read source and translated chapters in a dedicated reader.
4. Generate concise chapter, directory, and book guides directly from chapter bodies.
5. Ask questions and use Chapter/Book Quiz to explain concepts, theorem meaning, proof strategy, and concept connections in natural language.

## Core User Flow

1. Import a Markdown book.
2. Start translation.
3. Open chapters in Reader mode.
4. Ask chapter or selection questions grounded in the source text.
5. Generate and read top-down guides.

## Run Locally

```bash
./install.sh
cp backend/.env.example backend/.env
./run.sh
```

Stop with `Ctrl+C` in the terminal running `./run.sh`.

`run.sh` defaults to running `alembic upgrade head` before the backend starts. This is aimed at local development.

Useful flags:

```bash
RUN_DB_MIGRATIONS=0 ./run.sh     # skip automatic migrations
DB_MIGRATION_MODE=check ./run.sh # keep app-side revision check enabled
```

## Doc Map

- `ARCHITECTURE.md`: runtime architecture and boundaries.
- `re_impl.md`: product scope and implementation intent.
- `docs/structured-learning-recent-changes.md`: historical change record.
