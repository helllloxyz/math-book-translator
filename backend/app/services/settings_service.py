import os
import json
import logging
from app.models.schema import SettingsRequest

logger = logging.getLogger("app.settings")

class SettingsService:
    SETTINGS_FILE = "settings.json"

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
                
                logger.info("Loaded settings from settings.json")
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
                existing["llm_profile"] = settings.llm_profile.model_dump(exclude_none=True)

            if settings.llm_profiles is not None:
                existing["llm_profiles"] = {
                    task: profile.model_dump(exclude_none=True)
                    for task, profile in settings.llm_profiles.items()
                }
                existing.pop("llm_profile", None)

            # Do not persist or expose legacy secret-bearing settings.
            for secret_key in ("providers", "api_keys", "api_key", "model_names", "model_name", "llm_provider"):
                existing.pop(secret_key, None)

            with open(SettingsService.SETTINGS_FILE, "w") as f:
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
            "llm_profiles": {}
        }

    @staticmethod
    def _public_settings(settings: dict):
        public = {
            "storage_path": settings.get("storage_path", os.getenv("STORAGE_DIR", "storage")),
            "llm_profile": settings.get("llm_profile", {}),
            "llm_profiles": settings.get("llm_profiles", {}),
        }
        return public
