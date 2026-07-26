import json
import re
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException

from app.models.schema import CredentialUpdateRequest, CredentialWriteRequest, SettingsRequest
from app.services.llm_credentials import (
    CredentialRecord,
    FileCredentialRegistry,
    FileProviderOptionsRegistry,
)
from app.services.settings_service import SettingsService

router = APIRouter()

CONVERSATION_STYLES_PATH = Path(__file__).resolve().parents[3] / "config" / "conversation-styles.json"
STYLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@router.get("/settings")
async def get_settings():
    return SettingsService.get_current_settings()


@router.post("/settings")
async def update_settings(settings: SettingsRequest):
    return await SettingsService.update_settings(settings)


@router.get("/provider-options")
async def get_provider_options():
    return FileProviderOptionsRegistry().load()


@router.get("/credentials")
async def list_credentials():
    return {"credentials": FileCredentialRegistry().summaries()}


@router.post("/credentials")
async def create_credential(payload: CredentialWriteRequest):
    registry = FileCredentialRegistry()
    return {
        "credential": registry.upsert(
            CredentialRecord(
                credential_id=payload.credential_id,
                provider_type=payload.provider_type,
                provider_id=payload.provider_id,
                api_key=payload.api_key,
                base_url=payload.base_url,
                default_model=payload.default_model,
                models=payload.models or [],
                headers=payload.headers or {},
            )
        )
    }


@router.put("/credentials/{credential_id}")
async def update_credential(credential_id: str, payload: CredentialUpdateRequest):
    registry = FileCredentialRegistry()
    try:
        existing = registry.get(credential_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown credential_id: {credential_id}") from exc

    next_id = payload.credential_id or credential_id
    return {
        "credential": registry.upsert(
            CredentialRecord(
                credential_id=next_id,
                provider_type=payload.provider_type or existing.provider_type,
                provider_id=payload.provider_id if payload.provider_id is not None else existing.provider_id,
                api_key=payload.api_key if payload.api_key is not None else existing.api_key,
                base_url=payload.base_url if payload.base_url is not None else existing.base_url,
                default_model=payload.default_model if payload.default_model is not None else existing.default_model,
                models=payload.models if payload.models is not None else existing.models,
                headers=payload.headers if payload.headers is not None else existing.headers,
            )
        )
    }


def _normalize_conversation_styles(raw_styles):
    if not isinstance(raw_styles, list):
        raise HTTPException(status_code=422, detail="Conversation styles must be a list")

    normalized = []
    seen_ids = set()
    for index, raw_style in enumerate(raw_styles):
        if not isinstance(raw_style, dict):
            raise HTTPException(status_code=422, detail=f"Style at index {index} must be an object")

        style_id = str(raw_style.get("id", "")).strip()
        label = str(raw_style.get("label", "")).strip()
        prompt = str(raw_style.get("prompt", "")).strip()
        description = str(raw_style.get("description", "") or "").strip()

        if not style_id or not label or not prompt:
            raise HTTPException(status_code=422, detail="Style id, label, and prompt are required")
        if not STYLE_ID_PATTERN.fullmatch(style_id):
            raise HTTPException(status_code=422, detail=f"Invalid style id: {style_id}")
        if style_id in seen_ids:
            raise HTTPException(status_code=422, detail=f"Duplicate style id: {style_id}")

        seen_ids.add(style_id)
        normalized.append(
            {
                "id": style_id,
                "label": label,
                "description": description,
                "prompt": prompt,
            }
        )

    return normalized


@router.get("/settings/conversation-styles")
async def get_conversation_styles():
    if not CONVERSATION_STYLES_PATH.exists():
        return []
    try:
        raw_styles = json.loads(CONVERSATION_STYLES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Conversation styles config is invalid JSON") from exc
    return _normalize_conversation_styles(raw_styles)


@router.put("/settings/conversation-styles")
async def update_conversation_styles(styles: list = Body(...)):
    normalized = _normalize_conversation_styles(styles)
    CONVERSATION_STYLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONVERSATION_STYLES_PATH.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
