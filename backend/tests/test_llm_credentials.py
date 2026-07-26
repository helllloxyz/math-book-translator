from app.services.llm_credentials import CredentialRecord, resolve_default_provider_profile


class StubCredentialRegistry:
    def __init__(self, records):
        self.records = records

    def list(self):
        return self.records


class StubProviderOptionsRegistry:
    def load(self):
        return {
            "provider_catalog": [
                {
                    "provider_id": "openai",
                    "default_model": "gpt-5.2",
                    "default_base_url": "https://api.openai.com/v1",
                },
                {
                    "provider_id": "deepseek",
                    "default_model": "deepseek-chat",
                    "default_base_url": "https://api.deepseek.com/v1",
                },
            ]
        }


def test_explicit_missing_profile_does_not_mix_model_with_fallback_credential():
    deepseek = CredentialRecord(
        credential_id="deepseek",
        provider_id="deepseek",
        provider_type="openai_compatible",
        api_key="secret",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=["deepseek-chat"],
    )

    profile = resolve_default_provider_profile(
        settings={
            "llm_profiles": {
                "default": {
                    "credential_id": "openai",
                    "provider_id": "openai",
                    "provider_type": "openai_compatible",
                    "model": "gpt-5.2",
                }
            }
        },
        credential_registry=StubCredentialRegistry([deepseek]),
        provider_options_registry=StubProviderOptionsRegistry(),
    )

    assert profile is None


def test_empty_profile_can_fallback_to_first_configured_credential_model():
    deepseek = CredentialRecord(
        credential_id="deepseek",
        provider_id="deepseek",
        provider_type="openai_compatible",
        api_key="secret",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        models=["deepseek-chat"],
    )

    profile = resolve_default_provider_profile(
        settings={"llm_profiles": {}},
        credential_registry=StubCredentialRegistry([deepseek]),
        provider_options_registry=StubProviderOptionsRegistry(),
    )

    assert profile is not None
    assert profile.provider_id == "deepseek"
    assert profile.model == "deepseek-chat"
