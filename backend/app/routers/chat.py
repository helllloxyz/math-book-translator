from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schema import AskLLMRequest, ChatRequest
from app.services.prompts import PromptId, PromptRegistry
from app.services.translator import TranslatorService

router = APIRouter()

CHAT_SYSTEM_PROMPT = PromptRegistry.get(PromptId.READER_CHAT).system
QUIZ_SYSTEM_PROMPT = PromptRegistry.get(PromptId.READER_QUIZ).system


def chat_system_prompt_for_mode(mode: str) -> str:
    return QUIZ_SYSTEM_PROMPT if mode == "quiz" else CHAT_SYSTEM_PROMPT


@router.post("/ask-llm")
async def ask_llm(request: AskLLMRequest):
    return await TranslatorService(task="chat").ask_llm(request.context, request.prompt)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return StreamingResponse(
        TranslatorService(task="quiz" if request.mode == "quiz" else "chat").stream_messages(
            system_prompt=chat_system_prompt_for_mode(request.mode),
            context=request.context,
            history=request.messages,
            temperature=0.3,
        ),
        media_type="text/plain",
    )
