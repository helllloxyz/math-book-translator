from app.routers.chat import chat_system_prompt_for_mode
from app.services.prompts import PromptId, PromptRegistry


def test_chat_system_prompt_for_mode_uses_quiz_prompt_only_for_quiz():
    assert chat_system_prompt_for_mode("quiz") == PromptRegistry.get(PromptId.READER_QUIZ).system
    assert chat_system_prompt_for_mode("chat") == PromptRegistry.get(PromptId.READER_CHAT).system
    assert chat_system_prompt_for_mode("unexpected") == PromptRegistry.get(PromptId.READER_CHAT).system
