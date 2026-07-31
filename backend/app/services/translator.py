import os
import logging
import inspect
from typing import AsyncIterator

from app.services.llm_credentials import FileCredentialRegistry, resolve_default_provider_profile
from app.services.llm_json import extract_json_candidate
from app.services.prompts import PromptId, PromptRegistry

logger = logging.getLogger("app.translator")


class LLMConfigurationError(RuntimeError):
    """Raised when an LLM-backed operation is requested before credentials are configured."""


class TranslatorService:
    @staticmethod
    def _uses_socks_proxy() -> bool:
        for key in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            value = os.getenv(key, "").strip().lower()
            if value.startswith("socks"):
                return True
        return False

    def __init__(self, task: str = "default"):
        from app.services.settings_service import SettingsService

        self.task = task
        settings = SettingsService.get_current_settings()
        profile = resolve_default_provider_profile(settings=settings, task=task)
        self.provider = profile.provider_id or profile.provider_type if profile else "unconfigured"
        self.client_type = profile.provider_type if profile else "openai_compatible"
        self.api_key = None
        self.model_name = profile.model if profile else None
        self.base_url = profile.base_url if profile else None
        self.default_headers = dict(profile.headers) if profile else {}

        if not self.api_key:
            if profile is None:
                logger.warning("No LLM credential configured")
                return
            try:
                from app.services.llm_credentials import FileCredentialRegistry

                self.api_key = FileCredentialRegistry().get(profile.credential_id).api_key
            except KeyError:
                logger.warning("Unknown LLM credential_id=%s", profile.credential_id)
                return
            if not self.api_key:
                logger.warning("Empty API key for credential_id=%s", profile.credential_id)
                return

        # Initialize clients based on type
        if self.client_type == "gemini":
            from google import genai

            self.gemini_client = genai.Client(api_key=self.api_key)
            self.model_name = self.model_name or "gemini-2.5-flash"
        elif self.client_type == "anthropic":
            import anthropic

            self.anthropic_client = anthropic.AsyncAnthropic(api_key=self.api_key)
            self.model_name = self.model_name or "claude-sonnet-4-6"
        else: # openai compatible
            import openai

            if self._uses_socks_proxy():
                try:
                    import socksio  # type: ignore # noqa: F401
                except ImportError as exc:
                    raise RuntimeError(
                        "SOCKS proxy is configured, but dependency 'socksio' is missing. "
                        "Run `pip install -r backend/requirements.txt` (or `pip install httpx[socks]`)."
                    ) from exc
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=self.default_headers or None,
            )
            if not self.model_name:
                self.model_name = "gpt-5.6-terra"

    @staticmethod
    def configuration_error(task: str = "default") -> str | None:
        from app.services.settings_service import SettingsService

        settings = SettingsService.get_current_settings()
        profile = resolve_default_provider_profile(settings=settings, task=task)
        if profile is None:
            return "Configure an LLM provider and model in Settings before starting translation."

        try:
            credential = FileCredentialRegistry().get(profile.credential_id)
        except KeyError:
            return (
                f"Configured LLM credential '{profile.credential_id}' was not found. "
                "Update the LLM settings before starting translation."
            )

        if not credential.api_key.strip():
            return (
                f"Configured LLM credential '{profile.credential_id}' has no API key. "
                "Add an API key in Settings before starting translation."
            )
        return None

    @staticmethod
    def require_configured(task: str = "default") -> None:
        error = TranslatorService.configuration_error(task)
        if error:
            raise LLMConfigurationError(error)

    def _log_request(self, operation: str, *, system_prompt: str, user_prompt: str) -> None:
        logger.info(
            "LLM request operation=%s provider=%s client_type=%s model=%s system_chars=%s user_chars=%s",
            operation,
            self.provider,
            self.client_type,
            self.model_name,
            len(system_prompt),
            len(user_prompt),
        )

    def _log_response(self, operation: str, content: str) -> None:
        logger.info(
            "LLM response operation=%s provider=%s client_type=%s model=%s response_chars=%s",
            operation,
            self.provider,
            self.client_type,
            self.model_name,
            len(content),
        )

    async def complete(self, user_prompt: str, system_prompt: str, temperature: float = 0.3) -> str:
        if not self.api_key:
            error = self.configuration_error(self.task)
            raise LLMConfigurationError(error or f"No API key configured for provider {self.provider}")

        self._log_request(
            "complete",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        if self.client_type == "gemini":
            content = await self._ask_gemini(user_prompt, system_prompt, temperature)
        elif self.client_type == "anthropic":
            content = await self._ask_anthropic(user_prompt, system_prompt, temperature)
        else:
            content = await self._ask_openai_compat(user_prompt, system_prompt, temperature)

        self._log_response("complete", content)
        return content

    async def translate_text(self, text: str) -> str:
        """
        Translates text from English to Chinese, preserving LaTeX.
        """
        if not self.api_key:
            error = self.configuration_error(self.task)
            raise LLMConfigurationError(error or f"No API key configured for provider {self.provider}")

        system_prompt = PromptRegistry.get(PromptId.TRANSLATE_CHAPTER).system

        logger.info(
            "Translating chunk provider=%s model=%s chars=%s",
            self.provider,
            self.model_name,
            len(text),
        )

        return await self.complete(text, system_prompt, temperature=0.3)

    async def _ask_openai_compat(self, text: str, system_prompt: str, temperature: float = 0.3) -> str:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content.strip()

    async def _ask_gemini(self, text: str, system_prompt: str, temperature: float = 0.3) -> str:
        response = await self.gemini_client.aio.models.generate_content(
            model=self.model_name,
            contents=text,
            config={
                'system_instruction': system_prompt,
                'temperature': temperature,
            }
        )
        return response.text.strip()

    async def _ask_anthropic(self, text: str, system_prompt: str, temperature: float = 0.3) -> str:
        response = await self.anthropic_client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": text}
            ],
            temperature=temperature
        )
        return response.content[0].text.strip()

    async def ask_llm(self, context: str, prompt: str) -> dict:
        """
        Ask the LLM a question based on a specific context.
        Returns a dict with 'title' and 'content'.
        """
        if not self.api_key:
            return {"title": "Error", "content": "Error: No API Key configured."}

        system_prompt = PromptRegistry.get(PromptId.ASK_JSON).system

        user_content = f"Context:\n{context}\n\nQuestion: {prompt}"

        raw_response = ""
        try:
            raw_response = await self.complete(user_content, system_prompt, temperature=0.3)
            data = extract_json_candidate(raw_response, validator=lambda value: isinstance(value, dict))
            return {
                "title": data.get("title", "Note"),
                "content": data.get("content", raw_response)
            }
        except ValueError:
            logger.warning(
                "Failed to parse LLM JSON provider=%s model=%s response_chars=%s",
                self.provider,
                self.model_name,
                len(raw_response),
            )
            return {"title": "AI Answer", "content": raw_response}
        except Exception as e:
            return {"title": "Error", "content": f"Error communicating with AI ({self.provider}): {str(e)}"}

    async def stream_ask_llm(self, context: str, prompt: str):
        """
        Streams the LLM response for a question based on context.
        Yields chunks of the answer (Markdown).
        """
        if not self.api_key:
            yield "Error: No API Key configured."
            return

        system_prompt = PromptRegistry.get(PromptId.READER_CHAT).system

        try:
            async for chunk in self.stream_messages(
                system_prompt=system_prompt,
                context=context,
                history=[{"role": "user", "content": prompt}],
                temperature=0.3,
            ):
                yield chunk
        except Exception as e:
            logger.error(
                "Streaming ask error provider=%s model=%s context_chars=%s prompt_chars=%s error=%s",
                self.provider,
                self.model_name,
                len(context),
                len(prompt),
                e,
                exc_info=True,
            )
            yield f"\n\n[Error: {str(e)}]"

    async def _stream_openai_compat(self, text: str, system_prompt: str, temperature: float = 0.3):
        stream = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=temperature,
            stream=True
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def _stream_openai_compat_messages(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        temperature: float = 0.3,
    ):
        stream = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            temperature=temperature,
            stream=True
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def _create_gemini_content_stream(self, *, contents, system_prompt: str, temperature: float):
        response = self.gemini_client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
            config={
                'system_instruction': system_prompt,
                'temperature': temperature,
            },
        )
        if inspect.isawaitable(response):
            response = await response
        return response

    async def _stream_gemini(self, text: str, system_prompt: str, temperature: float = 0.3):
        response = await self._create_gemini_content_stream(
            contents=text,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_gemini_messages(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        temperature: float = 0.3,
    ):
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ]
        response = await self._create_gemini_content_stream(
            contents=contents,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_anthropic(self, text: str, system_prompt: str, temperature: float = 0.3):
        async with self.anthropic_client.messages.stream(
            model=self.model_name,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": text}
            ],
            temperature=temperature
        ) as stream:
            async for chunk in stream.text_stream:
                yield chunk

    async def _stream_anthropic_messages(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        temperature: float = 0.3,
    ):
        async with self.anthropic_client.messages.stream(
            model=self.model_name,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            temperature=temperature
        ) as stream:
            async for chunk in stream.text_stream:
                yield chunk

    def _serialize_chat_prompt(self, context: str, history: list[dict]) -> str:
        sections = [f"Context:\n{context.strip()}"]
        for msg in history:
            role = str(msg.get("role", "user")).strip() or "user"
            content = str(msg.get("content", "")).strip()
            sections.append(f"{role.capitalize()}:\n{content}")
        return "\n\n".join(sections)

    def _build_chat_messages(self, context: str, history: list[dict]) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if context.strip():
            messages.append({"role": "user", "content": f"Context:\n{context.strip()}"})

        for msg in history:
            role = str(msg.get("role", "user")).strip()
            if role not in {"user", "assistant"}:
                role = "user"
            content = str(msg.get("content", "")).strip()
            if content:
                messages.append({"role": role, "content": content})
        return messages

    async def stream_messages(
        self,
        system_prompt: str,
        context: str,
        history: list[dict],
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            yield "Error: No API Key configured."
            return

        messages = self._build_chat_messages(context, history)
        user_prompt = self._serialize_chat_prompt(context, history)
        self._log_request(
            "stream_messages",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        try:
            if self.client_type == "gemini":
                async for chunk in self._stream_gemini_messages(messages, system_prompt, temperature):
                    yield chunk
            elif self.client_type == "anthropic":
                async for chunk in self._stream_anthropic_messages(messages, system_prompt, temperature):
                    yield chunk
            else:
                async for chunk in self._stream_openai_compat_messages(messages, system_prompt, temperature):
                    yield chunk
        except Exception as e:
            logger.error(
                "Chat streaming error provider=%s model=%s context_chars=%s history_messages=%s error=%s",
                self.provider,
                self.model_name,
                len(context),
                len(history),
                e,
                exc_info=True,
            )
            yield f"\n\n[Error: {str(e)}]"

    async def stream_chat(self, context: str, history: list[dict]):
        """
        Streams the LLM response for a chat conversation.
        history: list of {"role": "user"/"assistant", "content": "..."}
        """
        if not self.api_key:
            yield "Error: No API Key configured."
            return

        system_prompt = PromptRegistry.get(PromptId.READER_CHAT).system

        async for chunk in self.stream_messages(
            system_prompt=system_prompt,
            context=context,
            history=history,
            temperature=0.3,
        ):
            yield chunk

    async def generate_title(self, context: str, prompt: str) -> str:
        """
        Generates a short title for a note based on context and prompt.
        """
        if not self.api_key:
            return "Note"

        system_prompt = PromptRegistry.get(PromptId.NOTE_TITLE).system
        
        content = f"Context:\n{context[:500]}\n\nQuestion: {prompt}"
        
        try:
            res = await self.complete(content, system_prompt, temperature=0.3)
            return res.strip()
        except:
            return "Note"
