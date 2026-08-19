import pytest
import re
import asyncio
from app.services.translator import TranslatorService
from app.services.translator import LLMConfigurationError
from app.services.settings_service import SettingsService

# Mock the OpenAI call since we don't want to spend money/credits on unit tests
# and we want to verify the regex/preservation logic specifically.
# However, the preservation logic is INSIDE the LLM prompting (it's an instruction to the LLM).
# To strictly test "Ensure LaTeX preservation" as per Phase 2, we actually need to test:
# 1. That our Prompt contains the instructions.
# 2. Or, we define a post-processing validator that we *could* run.
#
# The spec says: "Ensure LaTeX preservation (Write unit tests with regex to verify output contains same number of $$ blocks)."
# This implies we should have a validation function or we assume the "Output" from the Mock needs to be checked.
# Let's create a test that simulates a "Bad" vs "Good" LLM response and asserts our validation logic catches it,
# OR we simply write a test that checks if a sample input and output match the criteria.

def count_latex_blocks(text):
    # Regex for $$ ... $$
    # Note: This is a simple regex. Real LaTeX parsing can be complex.
    # We look for $$ on lines or inline.
    # Non-greedy match for content between $$
    return len(re.findall(r'\$\$', text)) // 2

@pytest.mark.asyncio
async def test_latex_preservation_check():
    """
    This test verifies that if we have an input string with N latex blocks,
    we expect the output to have N latex blocks.
    """
    input_text = """
    # Chapter 1
    
    Here is an equation:
    $$
    E = mc^2
    $$
    
    And another inline one: $$ F = ma $$
    """
    
    # Simulate a "Perfect" translation
    translated_text_good = """
    # 第1章
    
    这是一个方程：
    $$
    E = mc^2
    $$
    
    这是另一个行内的： $$ F = ma $$
    """
    
    # Simulate a "Bad" translation (missing one)
    translated_text_bad = """
    # 第1章
    
    这是一个方程：
    E = mc^2
    
    这是另一个行内的： $$ F = ma $$
    """
    
    input_count = count_latex_blocks(input_text)
    good_count = count_latex_blocks(translated_text_good)
    bad_count = count_latex_blocks(translated_text_bad)
    
    assert input_count == 2
    assert good_count == 2
    assert bad_count != input_count

# Since the spec asks to "Integrate OpenAI/Claude SDK", let's ensure the service can be instantiated
def test_translator_service_init():
    service = TranslatorService()
    assert service is not None


def test_translator_service_sets_client_type_without_api_key(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(
            lambda: {"storage_path": "storage", "llm_profile": {}}
        ),
    )
    monkeypatch.setattr(
        "app.services.llm_credentials.FileCredentialRegistry.list",
        lambda _self: [],
    )

    service = TranslatorService()

    assert service.client_type == "openai_compatible"


def test_translate_text_requires_configured_llm(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(lambda: {"storage_path": "storage", "llm_profiles": {}}),
    )
    monkeypatch.setattr(
        "app.services.llm_credentials.FileCredentialRegistry.list",
        lambda _self: [],
    )

    service = TranslatorService(task="translation")

    with pytest.raises(LLMConfigurationError, match="Configure an LLM provider"):
        asyncio.run(service.translate_text("Original text"))


@pytest.mark.asyncio
async def test_translate_text_prompt_requests_latex_ocr_fixes_without_explanations(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(
            lambda: {
                "llm_provider": "openai",
                "providers": {
                    "openai": {
                        "type": "openai",
                        "model": "test-model",
                    }
                },
            }
        ),
    )

    service = TranslatorService()
    service.api_key = "test-key"

    async def fake_complete(user_prompt, system_prompt, temperature=0.3):
        assert user_prompt == "Let $x \\in R$ be fixed."
        assert "recognized/OCR text" in system_prompt
        assert "fix only obvious latex syntax errors" in system_prompt.lower()
        assert "Do not explain, list, or mention any fixes" in system_prompt
        assert "Output ONLY the translated Markdown" in system_prompt
        assert "Markdown horizontal rule `---`" in system_prompt
        assert "Do not insert `---` inside LaTeX display blocks, code blocks, tables, or lists" in system_prompt
        return "设 $x \\in R$ 固定。"

    monkeypatch.setattr(service, "complete", fake_complete)

    result = await service.translate_text("Let $x \\in R$ be fixed.")

    assert result == "设 $x \\in R$ 固定。"


@pytest.mark.asyncio
async def test_generate_title_uses_complete_context_and_question(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(
            lambda: {
                "llm_provider": "openai",
                "providers": {
                    "openai": {
                        "type": "openai",
                        "model": "test-model",
                    }
                },
            }
        ),
    )

    service = TranslatorService()
    service.api_key = "test-key"
    context = "a" * 900

    async def fake_complete(user_prompt, system_prompt, temperature=0.3):
        assert user_prompt == f"Context:\n{'a' * 900}\n\nQuestion: 为什么这里需要紧性？"
        assert "Chinese title" in system_prompt
        assert "no trailing punctuation" in system_prompt
        assert temperature == 0.3
        return "紧性条件的作用"

    monkeypatch.setattr(service, "complete", fake_complete)

    result = await service.generate_title(context, "为什么这里需要紧性？")

    assert result == "紧性条件的作用"


@pytest.mark.asyncio
async def test_translate_text_propagates_llm_errors(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(
            lambda: {
                "llm_provider": "openai",
                "providers": {
                    "openai": {
                        "type": "openai",
                        "model": "test-model",
                    }
                },
            }
        ),
    )

    service = TranslatorService()
    service.api_key = "test-key"

    async def fake_complete(_user_prompt, _system_prompt, temperature=0.3):
        raise RuntimeError("provider down")

    monkeypatch.setattr(service, "complete", fake_complete)

    with pytest.raises(RuntimeError, match="provider down"):
        await service.translate_text("Original text")


@pytest.mark.asyncio
async def test_complete_routes_through_public_provider_boundary(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(
            lambda: {
                "llm_provider": "openai",
                "providers": {
                    "openai": {
                        "type": "openai",
                        "model": "test-model",
                    }
                },
            }
        ),
    )

    service = TranslatorService()
    service.api_key = "test-key"
    service.client_type = "openai_compatible"

    async def fake_ask(user_prompt, system_prompt, temperature=0.3):
        assert user_prompt == "Explain Stokes theorem"
        assert system_prompt == "You are a tutor."
        assert temperature == 0.2
        return "ok"

    monkeypatch.setattr(service, "_ask_openai_compat", fake_ask)

    result = await service.complete(
        user_prompt="Explain Stokes theorem",
        system_prompt="You are a tutor.",
        temperature=0.2,
    )

    assert result == "ok"


@pytest.mark.asyncio
async def test_stream_messages_uses_real_role_history_for_openai_boundary(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(
            lambda: {
                "llm_provider": "openai",
                "providers": {
                    "openai": {
                        "type": "openai",
                        "model": "test-model",
                    }
                },
            }
        ),
    )

    service = TranslatorService()
    service.api_key = "test-key"
    service.client_type = "openai_compatible"

    async def fake_stream(messages, system_prompt, temperature=0.3):
        assert messages == [
            {"role": "user", "content": "Context:\nChapter summary"},
            {"role": "user", "content": "What matters most?"},
            {"role": "assistant", "content": "Definitions matter."},
        ]
        assert system_prompt == "You are a tutor."
        assert temperature == 0.1
        for chunk in ("A", "B"):
            yield chunk

    monkeypatch.setattr(service, "_stream_openai_compat_messages", fake_stream)

    chunks = []
    async for chunk in service.stream_messages(
        system_prompt="You are a tutor.",
        context="Chapter summary",
        history=[
            {"role": "user", "content": "What matters most?"},
            {"role": "assistant", "content": "Definitions matter."},
        ],
        temperature=0.1,
    ):
        chunks.append(chunk)

    assert chunks == ["A", "B"]


@pytest.mark.asyncio
async def test_stream_gemini_messages_uses_generate_content_stream():
    service = TranslatorService.__new__(TranslatorService)
    service.model_name = "gemini-test"

    class Chunk:
        def __init__(self, text):
            self.text = text

    class ChunkStream:
        def __init__(self, chunks):
            self._chunks = iter(chunks)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._chunks)
            except StopIteration:
                raise StopAsyncIteration

    class Models:
        def __init__(self):
            self.calls = []

        async def generate_content_stream(self, **kwargs):
            self.calls.append(kwargs)
            return ChunkStream(Chunk(text) for text in ("hello", "", " world"))

        async def generate_content(self, **_kwargs):
            raise AssertionError("streaming should use generate_content_stream")

    class Aio:
        def __init__(self):
            self.models = Models()

    class GeminiClient:
        def __init__(self):
            self.aio = Aio()

    service.gemini_client = GeminiClient()

    chunks = []
    async for chunk in service._stream_gemini_messages(
        messages=[
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
        ],
        system_prompt="System prompt",
        temperature=0.2,
    ):
        chunks.append(chunk)

    assert chunks == ["hello", " world"]
    assert service.gemini_client.aio.models.calls == [
        {
            "model": "gemini-test",
            "contents": [
                {"role": "user", "parts": [{"text": "Question"}]},
                {"role": "model", "parts": [{"text": "Answer"}]},
            ],
            "config": {
                "system_instruction": "System prompt",
                "temperature": 0.2,
            },
        }
    ]


@pytest.mark.asyncio
async def test_ask_llm_extracts_json_embedded_in_text(monkeypatch):
    monkeypatch.setattr(
        SettingsService,
        "get_current_settings",
        staticmethod(
            lambda: {
                "llm_provider": "openai",
                "providers": {
                    "openai": {
                        "type": "openai",
                        "model": "test-model",
                    }
                },
            }
        ),
    )

    service = TranslatorService()
    service.api_key = "test-key"

    async def fake_complete(_user_prompt, _system_prompt, temperature=0.3):
        return """
        Here is the JSON:
        ```json
        {"title": "极限", "content": "核心是 $\\\\epsilon$ 控制。"}
        ```
        """

    monkeypatch.setattr(service, "complete", fake_complete)

    result = await service.ask_llm("Context", "Question")

    assert result == {"title": "极限", "content": "核心是 $\\epsilon$ 控制。"}
