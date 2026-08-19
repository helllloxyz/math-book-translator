import os
import json
import logging
from pathlib import Path

from app.models.schema import SettingsRequest
from app.services.llm_credentials import FileCredentialRegistry

logger = logging.getLogger("app.settings")

class SettingsService:
    SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.json")

    @staticmethod
    def load_settings():
        """Load non-secret settings from settings.json."""
        if not os.path.exists(SettingsService.SETTINGS_FILE):
            return {}

        try:
            with open(SettingsService.SETTINGS_FILE, "r") as f:
                settings = json.load(f)

                if settings.get("storage_path"):
                    os.environ["STORAGE_DIR"] = settings["storage_path"]
                
                logger.debug("Loaded settings from settings.json")
                return settings
        except Exception as e:
            logger.error(f"Failed to load settings.json: {e}")
            return {}

    @staticmethod
    async def update_settings(settings: SettingsRequest):
        """Update non-secret settings and persist to settings.json."""
        try:
            # Load existing to merge
            existing = {}
            if os.path.exists(SettingsService.SETTINGS_FILE):
                with open(SettingsService.SETTINGS_FILE, "r") as f:
                    existing = json.load(f)
            
            # Update fields
            if settings.storage_path:
                existing["storage_path"] = settings.storage_path
                os.environ["STORAGE_DIR"] = settings.storage_path

            if settings.llm_profile is not None:
                existing["llm_profile"] = SettingsService._sanitize_profile(
                    settings.llm_profile.model_dump(exclude_none=True)
                )

            if settings.llm_profiles is not None:
                requested_profiles = {
                    task: profile.model_dump(exclude_none=True)
                    for task, profile in settings.llm_profiles.items()
                }
                existing["llm_profiles"] = SettingsService._sanitize_profiles(requested_profiles)
                existing.pop("llm_profile", None)

            if settings.learning_profile_enabled is not None:
                existing["learning_profile_enabled"] = bool(settings.learning_profile_enabled)

            # Do not persist or expose legacy secret-bearing settings.
            for secret_key in ("providers", "api_keys", "api_key", "model_names", "model_name", "llm_provider"):
                existing.pop(secret_key, None)

            settings_path = Path(SettingsService.SETTINGS_FILE)
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with settings_path.open("w") as f:
                json.dump(existing, f, indent=2)
                
            return {"message": "Settings updated"}
        except Exception as e:
            logger.error(f"Failed to save settings.json: {e}")
            raise e

    @staticmethod
    def get_current_settings():
        if os.path.exists(SettingsService.SETTINGS_FILE):
            try:
                with open(SettingsService.SETTINGS_FILE, "r") as f:
                    return SettingsService._public_settings(json.load(f))
            except:
                pass
        
        return {
            "storage_path": os.getenv("STORAGE_DIR", "storage"),
            "llm_profiles": {},
            "learning_profile_enabled": False,
        }

    @staticmethod
    def _public_settings(settings: dict):
        public = {
            "storage_path": settings.get("storage_path", os.getenv("STORAGE_DIR", "storage")),
            "llm_profile": SettingsService._sanitize_profile(settings.get("llm_profile", {})),
            "llm_profiles": SettingsService._sanitize_profiles(settings.get("llm_profiles", {})),
            "learning_profile_enabled": bool(settings.get("learning_profile_enabled", False)),
        }
        return public

    @staticmethod
    def learning_profile_enabled() -> bool:
        return bool(SettingsService.get_current_settings().get("learning_profile_enabled", False))

    @staticmethod
    def _configured_credential_keys() -> set[str]:
        keys = set()
        for credential in FileCredentialRegistry().list():
            if not credential.api_key.strip():
                continue
            keys.add(credential.credential_id)
            if credential.provider_id:
                keys.add(credential.provider_id)
        return keys

    @staticmethod
    def _sanitize_profile(profile: dict) -> dict:
        if not isinstance(profile, dict) or not profile:
            return {}
        configured_keys = SettingsService._configured_credential_keys()
        credential_id = str(profile.get("credential_id") or "").strip()
        provider_id = str(profile.get("provider_id") or "").strip()
        if credential_id not in configured_keys and provider_id not in configured_keys:
            return {}
        return dict(profile)

    @staticmethod
    def _sanitize_profiles(profiles: dict) -> dict:
        if not isinstance(profiles, dict):
            return {}
        configured_keys = SettingsService._configured_credential_keys()
        sanitized = {}
        for task, profile in profiles.items():
            if not isinstance(profile, dict) or not profile:
                continue
            credential_id = str(profile.get("credential_id") or "").strip()
            provider_id = str(profile.get("provider_id") or "").strip()
            if credential_id in configured_keys or provider_id in configured_keys:
                sanitized[task] = dict(profile)
        return sanitized
