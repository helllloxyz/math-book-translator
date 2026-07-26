from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
PRIVATE_CONFIG_DIR = REPO_ROOT / "backend" / "config"
DEFAULT_CREDENTIALS_PATH = PRIVATE_CONFIG_DIR / "llm_credentials.json"
DEFAULT_PROVIDER_OPTIONS_PATH = CONFIG_DIR / "llm_provider_options.json"
DEFAULT_LLM_TASK = "default"


@dataclass(slots=True)
class CredentialRecord:
    credential_id: str
    provider_type: str
    api_key: str
    provider_id: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    models: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderProfile:
    provider_type: str
    model: str
    credential_id: str
    provider_id: str | None = None
    base_url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class FileCredentialRegistry:
    def __init__(self, path: Path = DEFAULT_CREDENTIALS_PATH) -> None:
        self.path = path

    def list(self) -> list[CredentialRecord]:
        payload = self._read_payload()
        records = []
        for item in payload.get("credentials", []):
            records.append(
                CredentialRecord(
                    credential_id=str(item["credential_id"]),
                    provider_type=str(item.get("provider_type") or "openai_compatible"),
                    provider_id=item.get("provider_id"),
                    api_key=str(item.get("api_key") or ""),
                    base_url=item.get("base_url"),
                    default_model=item.get("default_model"),
                    models=list(item.get("models") or []),
                    headers=dict(item.get("headers") or {}),
                )
            )
        return records

    def get(self, credential_id: str) -> CredentialRecord:
        for record in self.list():
            if record.credential_id == credential_id:
                return record
        raise KeyError(f"Unknown credential_id: {credential_id}")

    def summaries(self) -> list[dict[str, Any]]:
        summaries = []
        for record in self.list():
            summary: dict[str, Any] = {
                "credential_id": record.credential_id,
                "provider_type": record.provider_type,
                "provider_id": record.provider_id,
                "base_url": record.base_url,
                "default_model": record.default_model,
                "models": record.models,
                "has_api_key": bool(record.api_key),
                "has_headers": bool(record.headers),
            }
            summaries.append({key: value for key, value in summary.items() if value not in (None, [], "")})
        return summaries

    def upsert(self, record: CredentialRecord) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._read_payload()
        credentials = [
            item
            for item in payload.get("credentials", [])
            if item.get("credential_id") != record.credential_id
        ]
        credentials.append(
            {
                "credential_id": record.credential_id,
                "provider_type": record.provider_type,
                "provider_id": record.provider_id,
                "api_key": record.api_key,
                "base_url": record.base_url,
                "default_model": record.default_model,
                "models": record.models,
                "headers": record.headers,
            }
        )
        self.path.write_text(
            json.dumps({"credentials": credentials}, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return self.summarize_record(record)

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"credentials": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    @staticmethod
    def summarize_record(record: CredentialRecord) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "credential_id": record.credential_id,
            "provider_type": record.provider_type,
            "provider_id": record.provider_id,
            "base_url": record.base_url,
            "default_model": record.default_model,
            "models": record.models,
            "has_api_key": bool(record.api_key),
            "has_headers": bool(record.headers),
        }
        return {key: value for key, value in summary.items() if value not in (None, [], "")}


class FileProviderOptionsRegistry:
    def __init__(self, path: Path = DEFAULT_PROVIDER_OPTIONS_PATH) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"provider_catalog": []}
        return json.loads(self.path.read_text(encoding="utf-8"))


def resolve_default_provider_profile(
    *,
    settings: dict[str, Any],
    task: str = DEFAULT_LLM_TASK,
    credential_registry: FileCredentialRegistry | None = None,
    provider_options_registry: FileProviderOptionsRegistry | None = None,
) -> ProviderProfile | None:
    credentials = credential_registry or FileCredentialRegistry()
    provider_options = (provider_options_registry or FileProviderOptionsRegistry()).load()
    llm_profile = _settings_profile_for_task(settings, task)
    credential_id = str(llm_profile.get("credential_id") or "").strip()
    provider_id = str(llm_profile.get("provider_id") or "").strip() or None
    model = str(llm_profile.get("model") or "").strip()

    picked: CredentialRecord | None = None
    records = credentials.list()
    requires_configured_profile = bool(credential_id or provider_id)
    if credential_id:
        picked = next((record for record in records if record.credential_id == credential_id), None)
    if picked is None and provider_id:
        picked = next((record for record in records if record.provider_id == provider_id), None)
    if picked is None and requires_configured_profile:
        return None
    if picked is None and records:
        picked = records[0]
    if picked is None:
        return None

    resolved_model = model or picked.default_model or _catalog_default_model(provider_options, picked.provider_id) or ""
    if not resolved_model and picked.models:
        resolved_model = picked.models[0]
    if not resolved_model:
        return None

    base_url = picked.base_url or _catalog_default_base_url(provider_options, picked.provider_id)
    return ProviderProfile(
        provider_type=picked.provider_type,
        provider_id=picked.provider_id,
        credential_id=picked.credential_id,
        model=resolved_model,
        base_url=base_url,
        headers=dict(picked.headers),
    )


def _settings_profile_for_task(settings: dict[str, Any], task: str) -> dict[str, Any]:
    profiles = settings.get("llm_profiles")
    if isinstance(profiles, dict):
        task_profile = profiles.get(task)
        if isinstance(task_profile, dict) and task_profile:
            return dict(task_profile)
        default_profile = profiles.get(DEFAULT_LLM_TASK)
        if isinstance(default_profile, dict) and default_profile:
            return dict(default_profile)
    return dict(settings.get("llm_profile") or {})


def _catalog_default_model(provider_options: dict[str, Any], provider_id: str | None) -> str | None:
    if not provider_id:
        return None
    for item in provider_options.get("provider_catalog", []):
        if isinstance(item, dict) and item.get("provider_id") == provider_id:
            return item.get("default_model")
    return None


def _catalog_default_base_url(provider_options: dict[str, Any], provider_id: str | None) -> str | None:
    if not provider_id:
        return None
    for item in provider_options.get("provider_catalog", []):
        if isinstance(item, dict) and item.get("provider_id") == provider_id:
            return item.get("default_base_url")
    return None
