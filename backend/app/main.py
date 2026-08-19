import logging
import os
import sys
from contextlib import asynccontextmanager
from importlib import import_module
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import configure_logging
from app.models.base import engine
from app.routers import books, chapters, chat, guides, legacy, quiz, settings
from app.services.book_storage import BookStorage
from app.services.settings_service import SettingsService

configure_logging()
logger = logging.getLogger("app")


class SPAStaticFiles(StaticFiles):
    """Serve built frontend files and fall back to index.html for browser routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            headers = dict(scope.get("headers", []))
            accepts_html = b"text/html" in headers.get(b"accept", b"")
            if exc.status_code != 404 or not accepts_html:
                raise
            return await super().get_response("index.html", scope)


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


def _should_serve_frontend() -> bool:
    return os.getenv("SERVE_FRONTEND", "0").strip().lower() in ("1", "true", "yes", "on")


def _frontend_dist_dir() -> Path:
    configured = os.getenv("FRONTEND_DIST_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


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
    SettingsService.load_settings()
    migration_mode = _migration_mode()
    if migration_mode == "check":
        async with engine.connect() as conn:
            await conn.run_sync(_assert_database_is_current)
        logger.debug("Database migration state verified.")
    else:
        logger.debug("Database migration check skipped (DB_MIGRATION_MODE=%s).", migration_mode)
    logger.info("Math Book Translator backend is ready.")
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

    if _should_serve_frontend():
        frontend_dir = _frontend_dist_dir()
        if not (frontend_dir / "index.html").is_file():
            raise RuntimeError(
                f"Built frontend not found at {frontend_dir}. Run the installation script first."
            )
        app.mount("/", SPAStaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


app = create_app()
