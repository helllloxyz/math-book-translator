from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db
from app.models.schema import (
    LearningProfileCheckRequest,
    QuizAttemptRequest,
    QuizNextRequest,
    QuizSelectTargetRequest,
)
from app.services.learning_profile_service import LearningProfileService
from app.services.quiz_service import QuizGenerationError, QuizService

router = APIRouter()


@router.get("/books/{book_id}/quiz/profile/status")
async def get_learning_profile_status(book_id: int, db: AsyncSession = Depends(get_db)):
    status = await LearningProfileService.status(book_id, db)
    if status.get("book") is None and set(status) == {"book"}:
        raise HTTPException(status_code=404, detail="Book not found")
    return status


@router.post("/books/{book_id}/quiz/profile/analyze")
async def analyze_learning_profile(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await LearningProfileService.analyze(book_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return result


@router.post("/books/{book_id}/quiz/profile/check", status_code=202)
async def check_learning_profile(
    book_id: int,
    request: LearningProfileCheckRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    status = await LearningProfileService.status(book_id, db)
    if status.get("book") is None and set(status) == {"book"}:
        raise HTTPException(status_code=404, detail="Book not found")
    if not status.get("enabled"):
        return {**status, "scheduled": False}

    await LearningProfileService.sync_reading_progress(
        book_id,
        request.reading_statuses,
        request.current_chapter_id,
        db,
    )
    status = await LearningProfileService.status(book_id, db)
    scheduled = bool(status.get("should_analyze") and not status.get("analysis_running"))
    if scheduled:
        background_tasks.add_task(LearningProfileService.analyze_in_background, book_id)
    return {**status, "scheduled": scheduled}


@router.get("/books/{book_id}/quiz/profile")
async def get_learning_profile(book_id: int, db: AsyncSession = Depends(get_db)):
    result = await LearningProfileService.profile(book_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return result


@router.post("/chapters/{chapter_id}/quiz/next")
async def next_chapter_quiz(chapter_id: int, request: QuizNextRequest, db: AsyncSession = Depends(get_db)):
    try:
        question = await QuizService.next_chapter_question(
            chapter_id,
            quiz_mode=request.quiz_mode,
            question_type=request.question_type,
            personalization_context=request.personalization_context,
            db=db,
        )
    except QuizGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not question:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return QuizService.question_to_dict(question)


@router.post("/chapters/{chapter_id}/quiz/candidates")
async def quiz_candidates(chapter_id: int, request: QuizNextRequest, db: AsyncSession = Depends(get_db)):
    try:
        questions = await QuizService.generate_question_candidates(
            chapter_id,
            count=request.count,
            quiz_mode=request.quiz_mode,
            question_type=request.question_type,
            personalization_context=request.personalization_context,
            previous_questions=request.previous_questions,
            force_generate=request.force_generate,
            generation_count=request.generation_count,
            db=db,
        )
    except QuizGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if questions is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"questions": [QuizService.question_to_dict(question) for question in questions]}


@router.post("/quiz/questions/{question_id}/attempts")
async def create_quiz_attempt(question_id: int, request: QuizAttemptRequest, db: AsyncSession = Depends(get_db)):
    if not request.answer_text.strip():
        raise HTTPException(status_code=400, detail="answer_text is required")
    result = await QuizService.submit_attempt(
        question_id,
        request.answer_text,
        db,
        conversation_history=request.conversation_history,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    return result


@router.post("/books/{book_id}/quiz/select-target")
async def select_book_quiz_target(
    book_id: int,
    request: QuizSelectTargetRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await QuizService.select_target(
        book_id,
        personalization_context=request.personalization_context if request else None,
        db=db,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Book or chapter not found")
    return result
