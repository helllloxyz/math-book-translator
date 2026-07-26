import logging
import os
import sys
from contextlib import asynccontextmanager
from importlib import import_module
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.models.base import engine
from app.routers import books, chapters, chat, guides, legacy, quiz, settings
from app.services.book_storage import BookStorage
from app.services.settings_service import SettingsService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("backend_debug.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("app")


def _cors_allow_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost,http://127.0.0.1,http://localhost:5173,http://127.0.0.1:5173",
    )
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:5173"]


def _cors_allow_credentials(origins: list[str]) -> bool:
    configured = os.getenv("CORS_ALLOW_CREDENTIALS")
    if configured is not None:
        return configured.lower() in ("1", "true", "yes", "on")
    return "*" not in origins


def _import_external_alembic(module_name: str):
    backend_dir = str(Path(__file__).resolve().parents[1])
    original_path = list(sys.path)
    shadowed = sys.modules.pop("alembic", None)
    try:
        sys.path = [
            path
            for path in sys.path
            if str(Path(path or ".").resolve()) != backend_dir
        ]
        return import_module(module_name)
    finally:
        sys.path = original_path
        if shadowed is not None and "alembic" not in sys.modules:
            sys.modules["alembic"] = shadowed


def _alembic_config():
    Config = _import_external_alembic("alembic.config").Config
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./database.db"))
    return config


def _migration_mode() -> str:
    return os.getenv("DB_MIGRATION_MODE", "off").strip().lower() or "off"


def _assert_database_is_current(connection) -> None:
    MigrationContext = _import_external_alembic("alembic.runtime.migration").MigrationContext
    ScriptDirectory = _import_external_alembic("alembic.script").ScriptDirectory
    config = _alembic_config()
    script = ScriptDirectory.from_config(config)
    context = MigrationContext.configure(connection)
    current_heads = set(context.get_current_heads())
    expected_heads = set(script.get_heads())
    if current_heads != expected_heads:
        raise RuntimeError(
            "Database schema is not up to date. Run `cd backend && alembic upgrade head` before starting the app. "
            f"Current: {sorted(current_heads)} Expected: {sorted(expected_heads)}"
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting up application...")
    SettingsService.load_settings()
    migration_mode = _migration_mode()
    if migration_mode == "check":
        async with engine.connect() as conn:
            await conn.run_sync(_assert_database_is_current)
        logger.info("Database migration state verified.")
    else:
        logger.info("Database migration check skipped (DB_MIGRATION_MODE=%s).", migration_mode)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Math Book Translator", lifespan=lifespan)
    cors_origins = _cors_allow_origins()
    cors_allow_credentials = _cors_allow_credentials(cors_origins)

    storage_dir = BookStorage.static_dir()
    storage_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=storage_dir), name="static")
    config_dir = Path(__file__).resolve().parents[2] / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/config", StaticFiles(directory=config_dir), name="config")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(settings.router)
    app.include_router(books.router)
    app.include_router(chapters.router)
    app.include_router(chat.router)
    app.include_router(guides.router)
    app.include_router(quiz.router)
    app.include_router(legacy.router)
    return app


app = create_app()
