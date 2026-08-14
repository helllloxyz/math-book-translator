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

QUICK_INPUTS_PATH = Path(__file__).resolve().parents[3] / "config" / "quick-inputs.json"
QUICK_INPUT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


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


def _normalize_quick_inputs(raw_inputs):
    if not isinstance(raw_inputs, list):
        raise HTTPException(status_code=422, detail="Quick inputs must be a list")

    normalized = []
    seen_ids = set()
    for index, raw_input in enumerate(raw_inputs):
        if not isinstance(raw_input, dict):
            raise HTTPException(status_code=422, detail=f"Quick input at index {index} must be an object")
        if set(raw_input) != {"id", "label", "prompt"}:
            raise HTTPException(
                status_code=422,
                detail=f"Quick input at index {index} must contain only id, label, and prompt",
            )

        input_id = str(raw_input.get("id", "")).strip()
        label = str(raw_input.get("label", "")).strip()
        prompt = str(raw_input.get("prompt", "")).strip()

        if not input_id or not label or not prompt:
            raise HTTPException(status_code=422, detail="Quick input id, label, and prompt are required")
        if not QUICK_INPUT_ID_PATTERN.fullmatch(input_id):
            raise HTTPException(status_code=422, detail=f"Invalid quick input id: {input_id}")
        if input_id in seen_ids:
            raise HTTPException(status_code=422, detail=f"Duplicate quick input id: {input_id}")

        seen_ids.add(input_id)
        normalized.append(
            {
                "id": input_id,
                "label": label,
                "prompt": prompt,
            }
        )

    return normalized


@router.get("/settings/quick-inputs")
async def get_quick_inputs():
    if not QUICK_INPUTS_PATH.exists():
        return []
    try:
        raw_inputs = json.loads(QUICK_INPUTS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Quick inputs config is invalid JSON") from exc
    return _normalize_quick_inputs(raw_inputs)


@router.put("/settings/quick-inputs")
async def update_quick_inputs(inputs: list = Body(...)):
    normalized = _normalize_quick_inputs(inputs)
    QUICK_INPUTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUICK_INPUTS_PATH.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
