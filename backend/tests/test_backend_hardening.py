import json
import inspect
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schema import SettingsRequest
from app.services.book_service import BookService
from app.services.book_storage import BookStorage
from app.services.llm_credentials import CredentialRecord, FileCredentialRegistry
from app.services.settings_service import SettingsService


class FakeSession:
    def __init__(self):
        self.objects = []

    def add(self, obj):
        self.objects.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        obj.id = 123


class DummyAsyncConnection:
    async def run_sync(self, fn):
        return fn(object())


class DummyAsyncContextManager:
    async def __aenter__(self):
        return DummyAsyncConnection()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyAsyncEngine:
    def begin(self):
        return DummyAsyncContextManager()

    def connect(self):
        return DummyAsyncContextManager()


def _resolve_book_storage_helper(*names):
    for name in names:
        helper = getattr(BookStorage, name, None)
        if callable(helper):
            return helper
    pytest.skip(f"BookStorage helper not available yet: {', '.join(names)}")


def _call_book_storage_helper(helper, *args):
    signature = inspect.signature(helper)
    required_params = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.default is inspect._empty
        and parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    return helper(*args[: len(required_params)])


@pytest.mark.asyncio
async def test_create_book_from_content_sanitizes_uploaded_filename(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr("app.services.book_service.uuid.uuid4", lambda: "book-uuid")
    monkeypatch.setattr(
        "app.services.book_service.MarkdownSplitter.split_text",
        lambda _self, _content, **_kwargs: [],
    )

    await BookService.create_book_from_content("../escape.md", "# demo", FakeSession(), preflight=False)

    assert (tmp_path / "book-uuid" / "escape.md").exists()
    assert not (tmp_path / "escape.md").exists()


def test_raw_chapter_path_rejects_absolute_chapter_index(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    path = BookStorage.raw_chapter_path("book-uuid", "/etc/passwd")

    assert str(path).startswith(str(tmp_path / "book-uuid"))


def test_book_storage_manifest_helper_uses_book_root_when_available(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    helper = _resolve_book_storage_helper("manifest_path", "agent_manifest_path", "meta_path")

    path = Path(_call_book_storage_helper(helper, "book-uuid"))

    assert path == tmp_path / "book-uuid" / "00_meta.json"
    assert str(path).startswith(str(tmp_path / "book-uuid"))


def test_book_storage_history_helper_uses_book_root_when_available(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    helper = _resolve_book_storage_helper("history_path", "agent_history_path")

    path = Path(_call_book_storage_helper(helper, "book-uuid"))

    assert path == tmp_path / "book-uuid" / "history.jsonl"
    assert str(path).startswith(str(tmp_path / "book-uuid"))


def test_book_storage_static_helper_uses_storage_root_when_available(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    helper = _resolve_book_storage_helper("static_dir", "static_root", "static_storage_dir")

    path = Path(_call_book_storage_helper(helper))

    assert path == tmp_path


@pytest.mark.asyncio
async def test_update_settings_strips_legacy_secret_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        FileCredentialRegistry,
        "list",
        lambda _self: [
            CredentialRecord(
                credential_id="openai",
                provider_id="openai",
                provider_type="openai_compatible",
                api_key="configured",
            )
        ],
    )
    (tmp_path / SettingsService.SETTINGS_FILE).write_text(
        json.dumps(
            {
                "providers": {"openai": {"api_key": "k1"}},
                "api_keys": {"openai": "k1"},
                "llm_provider": "openai",
            }
        ),
        encoding="utf-8",
    )

    await SettingsService.update_settings(
        SettingsRequest(
            llm_profile={
                "provider_id": "openai",
                "provider_type": "openai_compatible",
                "credential_id": "openai",
                "model": "gpt-4o",
            }
        )
    )

    saved = json.loads((tmp_path / SettingsService.SETTINGS_FILE).read_text(encoding="utf-8"))
    assert "providers" not in saved
    assert "api_keys" not in saved
    assert saved["llm_profile"]["credential_id"] == "openai"


def test_get_current_settings_hides_profiles_without_configured_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(FileCredentialRegistry, "list", lambda _self: [])
    (tmp_path / SettingsService.SETTINGS_FILE).write_text(
        json.dumps(
            {
                "storage_path": "storage",
                "llm_profiles": {
                    "default": {
                        "provider_id": "gemini",
                        "provider_type": "gemini",
                        "credential_id": "gemini",
                        "model": "gemini-3-flash-preview",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsService.get_current_settings()

    assert settings["llm_profile"] == {}
    assert settings["llm_profiles"] == {}


@pytest.mark.asyncio
async def test_learning_profile_setting_defaults_off_and_persists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert SettingsService.get_current_settings()["learning_profile_enabled"] is False

    await SettingsService.update_settings(SettingsRequest(learning_profile_enabled=True))

    assert SettingsService.get_current_settings()["learning_profile_enabled"] is True
    saved = json.loads((tmp_path / SettingsService.SETTINGS_FILE).read_text(encoding="utf-8"))
    assert saved["learning_profile_enabled"] is True


def test_cors_disables_credentials_when_wildcard_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
    monkeypatch.delenv("CORS_ALLOW_CREDENTIALS", raising=False)

    app = create_app()
    cors_middleware = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")

    assert cors_middleware.kwargs["allow_origins"] == ["*"]
    assert cors_middleware.kwargs["allow_credentials"] is False


def test_startup_skips_migration_check_by_default(monkeypatch):
    create_all_calls = []
    migration_checks = []

    def fail_create_all(*_args, **_kwargs):
        create_all_calls.append("called")
        raise AssertionError("create_all should not be called during startup")

    def fake_assert_database_is_current(_connection):
        migration_checks.append("checked")

    monkeypatch.delenv("DB_MIGRATION_MODE", raising=False)
    monkeypatch.delenv("DB_MIGRATION_MODE", raising=False)
    monkeypatch.setattr("app.main.SettingsService.load_settings", lambda: None)
    monkeypatch.setattr("app.models.base.Base.metadata.create_all", fail_create_all)
    monkeypatch.setattr(
        "app.main._assert_database_is_current",
        fake_assert_database_is_current,
        raising=False,
    )
    monkeypatch.setattr("app.main.engine", DummyAsyncEngine())

    with TestClient(create_app()):
        pass

    assert migration_checks == []
    assert create_all_calls == []


def test_startup_checks_migration_state_when_enabled(monkeypatch):
    create_all_calls = []
    migration_checks = []

    def fail_create_all(*_args, **_kwargs):
        create_all_calls.append("called")
        raise AssertionError("create_all should not be called during startup")

    def fake_assert_database_is_current(_connection):
        migration_checks.append("checked")

    monkeypatch.setenv("DB_MIGRATION_MODE", "check")
    monkeypatch.setattr("app.main.SettingsService.load_settings", lambda: None)
    monkeypatch.setattr("app.models.base.Base.metadata.create_all", fail_create_all)
    monkeypatch.setattr(
        "app.main._assert_database_is_current",
        fake_assert_database_is_current,
        raising=False,
    )
    monkeypatch.setattr("app.main.engine", DummyAsyncEngine())

    with TestClient(create_app()):
        pass

    assert migration_checks == ["checked"]
    assert create_all_calls == []


def test_startup_raises_clear_error_when_database_is_not_migrated(monkeypatch):
    def fail_create_all(*_args, **_kwargs):
        raise AssertionError("create_all should not be called during startup")

    def fake_assert_database_is_current(_connection):
        raise RuntimeError("Database schema is not up to date.")

    monkeypatch.setenv("DB_MIGRATION_MODE", "check")
    monkeypatch.setattr("app.main.SettingsService.load_settings", lambda: None)
    monkeypatch.setattr("app.models.base.Base.metadata.create_all", fail_create_all)
    monkeypatch.setattr(
        "app.main._assert_database_is_current",
        fake_assert_database_is_current,
        raising=False,
    )
    monkeypatch.setattr("app.main.engine", DummyAsyncEngine())

    with pytest.raises(RuntimeError, match="Database schema is not up to date."):
        with TestClient(create_app()):
            pass
