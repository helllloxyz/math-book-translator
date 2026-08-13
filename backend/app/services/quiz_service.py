import json
import logging
import random
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import Book, Chapter, QuizAttempt, QuizQuestion
from app.services.chapter_source_service import ChapterSourceService
from app.services.guide_service import GuideService
from app.services.learning_profile_service import LearningProfileService
from app.services.llm_json import extract_json_candidate
from app.services.quiz_skill_registry import (
    BOOK_QUIZ_MODE,
    CHAPTER_QUIZ_MODE,
    QUIZ_SKILLS,
    canonical_question_type,
    get_quiz_skill,
    is_valid_question_type,
    normalize_quiz_mode,
    question_type_weights,
)
from app.services.translator import TranslatorService

logger = logging.getLogger("app.quiz_service")


class QuizGenerationError(RuntimeError):
    """Raised when the model cannot produce source-grounded quiz questions."""


class QuizService:
    CHAPTER_BANK_SPARSE_THRESHOLD = 3
    SPARSE_BANK_TYPE_COUNT = 3
    DEFAULT_BANK_GENERATION_COUNT = 6
    MAX_CANDIDATE_COUNT = 10
    GENERIC_SOURCE_SELECTION_PHRASES = (
        "请选择本章中的一个",
        "请选择本章中一个",
        "中的一个重要证明",
        "中的一个关键定理",
        "中的一个关键结论",
        "最核心的一个概念",
        "选择一个重要证明",
        "选择一个关键定理",
        "选择一个关键结论",
        "choose an important proof",
        "choose a key theorem",
        "choose a key result",
        "choose a core concept",
    )

    @staticmethod
    def question_to_dict(question: QuizQuestion) -> dict[str, Any]:
        skill = get_quiz_skill(question.question_type)
        return {
            "id": question.id,
            "book_id": question.book_id,
            "chapter_id": question.chapter_id,
            "quiz_mode": normalize_quiz_mode(getattr(question, "quiz_mode", None)),
            "source": question.source or "generated",
            "question_type": question.question_type,
            "question_type_label": skill.label,
            "difficulty": question.difficulty or "medium",
            "target_concepts": question.target_concepts or [],
            "question_text": question.question_text,
            "expected_points": question.expected_points or [],
            "common_mistakes": question.common_mistakes or [],
            "context_refs": question.context_refs or [],
            "evaluation_rubric": question.evaluation_rubric or {},
            "followup_strategy": question.followup_strategy or "",
            "answer_guidance": skill.answer_guidance,
        }

    @staticmethod
    async def _chapter_or_none(chapter_id: int, db: AsyncSession) -> Chapter | None:
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def _book_or_none(book_id: int, db: AsyncSession) -> Book | None:
        result = await db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def recent_question_texts(
        *,
        book_id: int,
        chapter_id: int,
        quiz_mode: str,
        db: AsyncSession,
        limit: int = 30,
    ) -> list[str]:
        result = await db.execute(
            select(QuizQuestion.question_text)
            .where(
                QuizQuestion.book_id == book_id,
                QuizQuestion.chapter_id == chapter_id,
                QuizQuestion.quiz_mode == normalize_quiz_mode(quiz_mode),
            )
            .order_by(QuizQuestion.created_at.desc())
            .limit(max(1, min(100, limit)))
        )
        return [str(text).strip() for text in result.scalars().all() if str(text or "").strip()]

    @staticmethod
    def weighted_random_question_type() -> str:
        weights = question_type_weights()
        total = sum(max(0.0, weight) for weight in weights.values())
        if total <= 0:
            return "concept_explain"
        target = random.random() * total
        cumulative = 0.0
        selected = "concept_explain"
        for question_type, weight in weights.items():
            cumulative += max(0.0, weight)
            selected = question_type
            if target <= cumulative:
                return question_type
        return selected

    @staticmethod
    def sparse_bank_question_types(selected_type: str) -> list[str]:
        ordered = [selected_type]
        weighted_types = sorted(
            question_type_weights().items(),
            key=lambda item: item[1],
            reverse=True,
        )
        for question_type, _weight in weighted_types:
            if question_type not in ordered:
                ordered.append(question_type)
            if len(ordered) >= QuizService.SPARSE_BANK_TYPE_COUNT:
                break
        return ordered

    @staticmethod
    def candidate_batch_question_types(selected_type: str, count: int) -> list[str]:
        ordered = [selected_type]
        for question_type, _weight in sorted(
            question_type_weights().items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            if question_type not in ordered:
                ordered.append(question_type)
        return [ordered[index % len(ordered)] for index in range(max(1, count))]

    @staticmethod
    async def _book_guide_text(book_uuid: str) -> str:
        guides = await GuideService.list_guides(book_uuid)
        parts = []
        for guide in guides:
            if guide.get("scope_type") != "book":
                continue
            try:
                data = await GuideService.read_guide(book_uuid, guide["filename"])
            except FileNotFoundError:
                continue
            parts.append(data.get("content", ""))
        return "\n\n".join(parts).strip()

    @staticmethod
    async def _chapter_guide_text(book_uuid: str, chapter_index: str) -> str:
        guides = await GuideService.list_guides(book_uuid)
        parts = []
        for guide in guides:
            if guide.get("scope_type") != "chapter" or str(guide.get("scope_id")) != str(chapter_index):
                continue
            try:
                data = await GuideService.read_guide(book_uuid, guide["filename"])
            except FileNotFoundError:
                continue
            parts.append(data.get("content", ""))
        return "\n\n".join(parts).strip()

    @staticmethod
    async def build_generation_context(
        book: Book,
        chapter: Chapter | None,
        question_type: str,
        quiz_mode: str = CHAPTER_QUIZ_MODE,
        *,
        include_skill_details: bool = True,
    ) -> str:
        skill = get_quiz_skill(question_type)
        mode = normalize_quiz_mode(quiz_mode)
        required_context = (
            ("chapter_body",)
            if mode == CHAPTER_QUIZ_MODE
            else skill.required_context
        )
        mode_goal = (
            "This is a Book Quiz: diagnose the learner's selected weak point in the book. "
            "Use the personalization context as a targeting instruction, but do not reveal private profile evidence in the question."
            if mode == BOOK_QUIZ_MODE
            else (
                "This is a Chapter Quiz: ask one focused teach-back question about the current chapter. "
                "Use the chapter body as the only source context."
            )
        )
        parts = [
            f"Book: {book.title}",
            f"Quiz mode: {mode}",
            f"Mode goal: {mode_goal}",
            f"Required context: {', '.join(required_context)}",
        ]
        if include_skill_details:
            parts.extend(
                [
                    f"Question type: {skill.question_type}",
                    f"Goal: {skill.goal}",
                    f"Type-specific generation instruction: {skill.generation_prompt}",
                    f"How the learner should answer: {skill.answer_guidance}",
                ]
            )
        if chapter:
            parts.append(
                f"Chapter: {chapter.chapter_index} {chapter.title_zh or chapter.title_en or ''}".strip()
            )
            chapter_source = await ChapterSourceService.chapter_context(
                book.uuid,
                chapter,
            )
            parts.extend(
                [
                    (
                        "Chapter body (direct source"
                        f", language={chapter_source['body_language']}"
                        "):"
                    ),
                    chapter_source["body"],
                ]
            )
            if mode == BOOK_QUIZ_MODE:
                parts.extend(
                    [
                        "Chapter guide:",
                        await QuizService._chapter_guide_text(book.uuid, chapter.chapter_index),
                    ]
                )
        if mode == BOOK_QUIZ_MODE:
            parts.extend(["Book guide:", await QuizService._book_guide_text(book.uuid)])
        return "\n\n".join(parts).strip()

    @staticmethod
    def normalize_question_data(
        data: dict[str, Any],
        *,
        book_id: int,
        chapter_id: int | None,
        question_type: str,
        quiz_mode: str,
        source: str,
    ) -> dict[str, Any]:
        skill = get_quiz_skill(question_type)
        mode = normalize_quiz_mode(quiz_mode)
        expected_points = data.get("expected_points") or data.get("expected_answer_points") or []
        if isinstance(expected_points, str):
            expected_points = [expected_points]
        if not expected_points:
            expected_points = list(skill.expected_points)
        target_concepts = data.get("target_concepts") or []
        if isinstance(target_concepts, str):
            target_concepts = [target_concepts]
        common_mistakes = data.get("common_mistakes") or []
        if isinstance(common_mistakes, str):
            common_mistakes = [common_mistakes]
        question_text = str(data.get("question_text") or data.get("question") or "").strip()
        if not question_text:
            raise ValueError("question_text is required")
        return {
            "book_id": book_id,
            "chapter_id": chapter_id,
            "quiz_mode": mode,
            "source": source,
            "question_type": skill.question_type,
            "difficulty": str(data.get("difficulty") or "medium"),
            "target_concepts": [str(item) for item in target_concepts if str(item).strip()],
            "question_text": question_text,
            "expected_points": [str(item) for item in expected_points if str(item).strip()],
            "common_mistakes": [str(item) for item in common_mistakes if str(item).strip()],
            "context_refs": data.get("context_refs") if isinstance(data.get("context_refs"), list) else [],
            "evaluation_rubric": data.get("evaluation_rubric")
            if isinstance(data.get("evaluation_rubric"), dict)
            else skill.evaluation_rubric,
            "followup_strategy": str(data.get("followup_strategy") or skill.next_step_rule),
        }

    @staticmethod
    async def generate_question(
        *,
        book: Book,
        chapter: Chapter | None,
        question_type: str,
        quiz_mode: str,
        db: AsyncSession,
        source: str = "generated",
        personalization_context: str | None = None,
    ) -> QuizQuestion:
        skill = get_quiz_skill(question_type)
        mode = normalize_quiz_mode(quiz_mode)
        context = await QuizService.build_generation_context(
            book,
            chapter,
            skill.question_type,
            mode,
        )
        if personalization_context:
            context = f"{context}\n\nPersonalization context:\n{personalization_context}"

        translator = TranslatorService(task="quiz")
        if not getattr(translator, "api_key", None):
            raise QuizGenerationError("Quiz 出题模型尚未配置。请先在设置中配置可用的 LLM。")
        system_prompt = (
            "You design one source-grounded Feynman-style teach-back question for a mathematics reader. "
            "Explicitly name the exact definition, named result, proof endpoint, construction, or related objects from "
            "the supplied chapter. Never ask the learner to choose a concept, theorem, result, or proof, and never use "
            "the chapter title as the only anchor. The learner must be able to answer in ordinary natural language, "
            "typically in 2-6 sentences. Never require a calculation, formula entry, or complete formal proof. Use only "
            "claims supported by the source, write in Chinese, and do not include the answer or profile evidence. Return "
            "strictly valid JSON with question_text, difficulty, target_concepts, expected_points, common_mistakes, and "
            "context_refs. Keep arrays concise. context_refs must quote a short heading, result name, or distinctive phrase "
            "that occurs verbatim in the chapter."
        )
        user_prompt = (
            f"{context}\n\n"
            f"Generate exactly one {skill.label} ({skill.question_type}) question.\n"
            f"Type-specific instruction: {skill.generation_prompt}\n"
            f"Evaluation focus: {skill.evaluation_prompt}"
        )
        raw = ""
        try:
            raw = await translator.complete(user_prompt, system_prompt, temperature=0.35)
            parsed = extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))
            quality_issues = QuizService._candidate_quality_issues(
                parsed,
                context,
                generic_anchors=(
                    book.title,
                    chapter.chapter_index if chapter else "",
                    chapter.title_zh or "" if chapter else "",
                    chapter.title_en or "" if chapter else "",
                ),
            )
            if quality_issues:
                raise ValueError("; ".join(quality_issues))
            normalized = QuizService.normalize_question_data(
                parsed,
                book_id=book.id,
                chapter_id=chapter.id if chapter else None,
                question_type=skill.question_type,
                quiz_mode=mode,
                source=source,
            )
        except Exception as exc:
            logger.warning(
                "Quiz question generation failed provider=%s model=%s response_chars=%s response_preview=%r error=%s",
                getattr(translator, "provider", "unknown"),
                getattr(translator, "model_name", "unknown"),
                len(raw),
                raw[:400],
                exc,
            )
            raise QuizGenerationError(f"Quiz 出题失败：{exc}") from exc

        question = QuizQuestion(**normalized)
        db.add(question)
        await db.commit()
        await db.refresh(question)
        return question

    @staticmethod
    def _candidate_quality_issues(
        data: dict[str, Any],
        source_context: str,
        *,
        generic_anchors: tuple[str, ...] = (),
    ) -> list[str]:
        question_text = " ".join(str(data.get("question_text") or data.get("question") or "").split())
        target_concepts = data.get("target_concepts") or []
        if isinstance(target_concepts, str):
            target_concepts = [target_concepts]
        raw_context_refs = data.get("context_refs")
        context_refs = raw_context_refs or []
        if isinstance(context_refs, str):
            context_refs = [context_refs]
        expected_points = data.get("expected_points") or data.get("expected_answer_points") or []
        if isinstance(expected_points, str):
            expected_points = [expected_points]

        issues = []
        if not question_text:
            issues.append("question_text is empty")
        if any(
            phrase.casefold() in question_text.casefold()
            for phrase in QuizService.GENERIC_SOURCE_SELECTION_PHRASES
        ):
            issues.append("question delegates source selection to the learner")
        anchors = [
            " ".join(str(value or "").split()).strip()
            for value in [*target_concepts, *context_refs]
            if " ".join(str(value or "").split()).strip()
        ]
        if not target_concepts:
            issues.append("target_concepts is empty")
        if not context_refs:
            issues.append("context_refs is empty")
        elif not isinstance(raw_context_refs, list):
            issues.append("context_refs must be a JSON array")
        if not expected_points:
            issues.append("expected_points is empty")
        generic_anchor_keys = {
            " ".join(str(value or "").split()).casefold()
            for value in generic_anchors
            if " ".join(str(value or "").split())
        }
        substantive_anchors = [
            anchor for anchor in anchors if anchor.casefold() not in generic_anchor_keys
        ]
        if not substantive_anchors:
            issues.append("the chapter or book title is the only source anchor")
        folded_context = source_context.casefold()
        if substantive_anchors and not any(
            anchor.casefold() in folded_context
            for anchor in substantive_anchors
            if len(anchor) >= 2
        ):
            issues.append("no target concept or context reference can be found in the supplied source")
        if substantive_anchors and not any(
            anchor.casefold() in question_text.casefold()
            for anchor in substantive_anchors
            if len(anchor) >= 2
        ):
            issues.append("question_text does not name a concrete source anchor")
        return issues

    @staticmethod
    def _is_reusable_bank_question(question: QuizQuestion) -> bool:
        source = str(question.source or "")
        question_text = " ".join(str(question.question_text or "").split())
        if source.endswith("_fallback"):
            return False
        if not question_text or not question.target_concepts or not question.context_refs or not question.expected_points:
            return False
        if any(
            phrase.casefold() in question_text.casefold()
            for phrase in QuizService.GENERIC_SOURCE_SELECTION_PHRASES
        ):
            return False
        return is_valid_question_type(question.question_type)

    @staticmethod
    async def choose_candidates_from_bank(
        *,
        book_id: int,
        chapter_id: int,
        question_type: str | None,
        quiz_mode: str,
        count: int,
        previous_questions: list[str] | None,
        db: AsyncSession,
        mark_seen: bool = True,
    ) -> list[QuizQuestion]:
        mode = normalize_quiz_mode(quiz_mode)
        query = select(QuizQuestion).where(
            QuizQuestion.book_id == book_id,
            QuizQuestion.chapter_id == chapter_id,
            QuizQuestion.quiz_mode == mode,
        )
        if question_type:
            query = query.where(QuizQuestion.question_type == canonical_question_type(question_type))
        result = await db.execute(
            query.order_by(
                QuizQuestion.correct_count.asc(),
                QuizQuestion.attempts_count.asc(),
                QuizQuestion.times_seen.asc(),
                QuizQuestion.created_at.asc(),
            )
        )
        questions = [
            question
            for question in result.scalars().all()
            if QuizService._is_reusable_bank_question(question)
        ]
        previous_keys = {
            " ".join(str(value or "").split()).casefold()
            for value in (previous_questions or [])
            if " ".join(str(value or "").split())
        }
        unseen = [
            question
            for question in questions
            if " ".join(str(question.question_text or "").split()).casefold() not in previous_keys
        ]
        repeated = [question for question in questions if question not in unseen]
        selected = (unseen + repeated)[: max(1, min(QuizService.MAX_CANDIDATE_COUNT, count))]
        if mark_seen and selected:
            now = datetime.utcnow()
            for question in selected:
                question.times_seen = int(question.times_seen or 0) + 1
                question.last_seen_at = now
            await db.commit()
            for question in selected:
                await db.refresh(question)
        return selected

    @staticmethod
    async def _generate_and_store_question_candidates(
        chapter_id: int,
        *,
        count: int,
        quiz_mode: str,
        question_type: str | None,
        personalization_context: str | None,
        previous_questions: list[str] | None,
        db: AsyncSession,
    ) -> list[QuizQuestion] | None:
        """Generate and persist a small, source-grounded candidate pool in one LLM call."""
        mode = normalize_quiz_mode(quiz_mode)
        candidate_count = max(1, min(QuizService.MAX_CANDIDATE_COUNT, int(count or 1)))
        chapter = await QuizService._chapter_or_none(chapter_id, db)
        if not chapter:
            return None
        book = await QuizService._book_or_none(chapter.book_id, db)
        if not book:
            return None
        if question_type and not is_valid_question_type(question_type):
            raise ValueError(f"Unsupported quiz question type: {question_type}")

        if question_type:
            selected_types = [canonical_question_type(question_type)] * candidate_count
        else:
            selected_types = QuizService.candidate_batch_question_types(
                QuizService.weighted_random_question_type(),
                candidate_count,
            )

        context = await QuizService.build_generation_context(
            book,
            chapter,
            selected_types[0],
            mode,
            include_skill_details=False,
        )
        if personalization_context:
            context = f"{context}\n\nPersonalization context:\n{personalization_context}"

        stored_questions = await QuizService.recent_question_texts(
            book_id=book.id,
            chapter_id=chapter.id,
            quiz_mode=mode,
            db=db,
        )
        old_questions = []
        for value in [*(previous_questions or []), *stored_questions]:
            normalized_text = " ".join(str(value or "").split()).strip()
            if normalized_text and normalized_text not in old_questions:
                old_questions.append(normalized_text[:800])
            if len(old_questions) >= 30:
                break

        type_specs = []
        for candidate_type in selected_types:
            skill = get_quiz_skill(candidate_type)
            type_specs.append(
                {
                    "question_type": skill.question_type,
                    "label": skill.label,
                    "generation_instruction": skill.generation_prompt,
                    "evaluation_focus": skill.evaluation_prompt,
                    "default_expected_points": skill.expected_points,
                }
            )

        translator = TranslatorService(task="quiz")
        parsed_questions: list[dict[str, Any]] = []
        system_prompt = (
            "You design a small set of source-grounded Feynman-style teach-back questions for a reader of a serious "
            "mathematics book. First identify the exact definition, named result, proof endpoint, construction, or pair "
            "of related objects in the supplied chapter body that each question will test. Every question must explicitly "
            "name that source anchor and include enough source-specific detail to be answerable without asking the learner "
            "to choose a concept, theorem, result, or proof. Never produce prompts such as 'choose an important proof', "
            "'choose a key theorem', or 'explain the chapter's core concept'. Do not use the chapter title as the only anchor. "
            "Every question must be answerable in ordinary natural language, typically in 2-6 sentences. Never require "
            "typing a formula, carrying out a calculation, filling a missing equation, reproducing notation, or writing a "
            "complete formal proof. Use only claims supported by the supplied source. If a requested question type is not "
            "supported by the chapter body, use another supported type and report that actual question_type; never invent a "
            "theorem or proof. Write in Chinese and do not include answers or expose learning-profile evidence. Questions "
            "must use different source anchors and must not repeat or lightly paraphrase a previous question. Return strictly "
            "valid JSON as {\"questions\": [...]}; a top-level JSON array is also accepted. Each item must contain "
            "question_type, question_text, difficulty, target_concepts, expected_points, common_mistakes, and context_refs. "
            "target_concepts must name the concrete mathematical objects being tested. context_refs must contain a short "
            "heading, definition/result name, or distinctive source phrase that occurs verbatim in the supplied chapter. "
            "Use 1-3 concise strings in each array. expected_points must be specific to that source anchor, not generic "
            "skill criteria. Do not add prose outside the JSON."
        )
        user_prompt = (
            f"{context}\n\n"
            f"Generate exactly {candidate_count} candidate questions.\n"
            f"Candidate specifications, in order:\n{json.dumps(type_specs, ensure_ascii=False)}\n\n"
            f"Previous questions that must not be repeated or lightly paraphrased:\n"
            f"{json.dumps(old_questions, ensure_ascii=False)}"
        )
        if not getattr(translator, "api_key", None):
            raise QuizGenerationError(
                "Quiz 出题模型尚未配置。请先在设置中配置可用的 LLM。"
            )
        validation_details: list[str] = []
        raw = ""
        for attempt in range(2):
            try:
                repair_prompt = ""
                if validation_details:
                    repair_prompt = (
                        "\n\nThe previous response was rejected for these reasons: "
                        f"{json.dumps(validation_details, ensure_ascii=False)}. Regenerate the full set."
                    )
                raw = await translator.complete(
                    f"{user_prompt}{repair_prompt}",
                    system_prompt,
                    temperature=0.35,
                )
                parsed = extract_json_candidate(
                    raw,
                    validator=lambda value: (
                        isinstance(value, list)
                        or (isinstance(value, dict) and isinstance(value.get("questions"), list))
                    ),
                    transform=lambda value: {"questions": value} if isinstance(value, list) else value,
                )
                parsed_questions = [item for item in parsed["questions"] if isinstance(item, dict)]
                validation_details = []
                if len(parsed_questions) != candidate_count:
                    validation_details.append(
                        f"expected {candidate_count} questions, received {len(parsed_questions)}"
                    )
                for index, item in enumerate(parsed_questions[:candidate_count]):
                    item_issues = QuizService._candidate_quality_issues(
                        item,
                        context,
                        generic_anchors=(
                            book.title,
                            chapter.chapter_index,
                            chapter.title_zh or "",
                            chapter.title_en or "",
                        ),
                    )
                    validation_details.extend(
                        f"question {index + 1}: {issue}" for issue in item_issues
                    )
                response_seen = {text.casefold() for text in old_questions}
                for index, item in enumerate(parsed_questions[:candidate_count]):
                    question_key = " ".join(
                        str(item.get("question_text") or item.get("question") or "").split()
                    ).casefold()
                    if question_key in response_seen:
                        validation_details.append(
                            f"question {index + 1}: repeats a previous or same-batch question"
                        )
                    response_seen.add(question_key)
                if not validation_details:
                    break
            except Exception as exc:
                validation_details = [f"{type(exc).__name__}: {exc}"]
                logger.warning(
                    "Quiz candidate generation failed attempt=%s provider=%s model=%s response_chars=%s "
                    "response_preview=%r error=%s",
                    attempt + 1,
                    getattr(translator, "provider", "unknown"),
                    getattr(translator, "model_name", "unknown"),
                    len(raw),
                    raw[:400],
                    exc,
                )
        if validation_details:
            logger.warning("Quiz candidate generation rejected: %s", validation_details)
            raise QuizGenerationError(f"Quiz 出题失败：{'；'.join(validation_details[:4])}")

        normalized_questions: list[dict[str, Any]] = []
        seen_texts = {text.casefold() for text in old_questions}
        for index, candidate_type in enumerate(selected_types):
            raw_data = parsed_questions[index]
            returned_type = raw_data.get("question_type")
            normalized_type = (
                canonical_question_type(returned_type)
                if is_valid_question_type(returned_type)
                else candidate_type
            )
            normalized = QuizService.normalize_question_data(
                raw_data,
                book_id=book.id,
                chapter_id=chapter.id,
                question_type=normalized_type,
                quiz_mode=mode,
                source="book_candidate_batch" if mode == BOOK_QUIZ_MODE else "chapter_candidate_batch",
            )
            normalized_key = " ".join(normalized["question_text"].split()).casefold()
            if normalized_key in seen_texts:
                raise QuizGenerationError(
                    "模型生成了重复题目，未写入题库，请重试。"
                )
            seen_texts.add(normalized_key)
            normalized_questions.append(normalized)

        questions = [QuizQuestion(**data, times_seen=0) for data in normalized_questions]
        for question in questions:
            db.add(question)
        await db.commit()
        for question in questions:
            await db.refresh(question)
        return questions

    @staticmethod
    async def generate_question_candidates(
        chapter_id: int,
        *,
        count: int,
        quiz_mode: str,
        question_type: str | None,
        personalization_context: str | None,
        previous_questions: list[str] | None,
        db: AsyncSession,
        force_generate: bool = False,
        generation_count: int = DEFAULT_BANK_GENERATION_COUNT,
    ) -> list[QuizQuestion] | None:
        """Serve Chapter Quiz from its persistent bank, filling the bank only when needed."""
        mode = normalize_quiz_mode(quiz_mode)
        candidate_count = max(1, min(QuizService.MAX_CANDIDATE_COUNT, int(count or 1)))
        bank_generation_count = max(
            candidate_count,
            min(QuizService.MAX_CANDIDATE_COUNT, int(generation_count or 1)),
        )
        chapter = await QuizService._chapter_or_none(chapter_id, db)
        if not chapter:
            return None
        book = await QuizService._book_or_none(chapter.book_id, db)
        if not book:
            return None

        if mode == BOOK_QUIZ_MODE:
            generated = await QuizService._generate_and_store_question_candidates(
                chapter_id,
                count=candidate_count,
                quiz_mode=mode,
                question_type=question_type,
                personalization_context=personalization_context,
                previous_questions=previous_questions,
                db=db,
            )
            now = datetime.utcnow()
            for question in generated:
                question.times_seen = int(question.times_seen or 0) + 1
                question.last_seen_at = now
            await db.commit()
            for question in generated:
                await db.refresh(question)
            return generated

        bank_questions = await QuizService.choose_candidates_from_bank(
            book_id=book.id,
            chapter_id=chapter.id,
            question_type=question_type,
            quiz_mode=mode,
            count=candidate_count,
            previous_questions=previous_questions,
            db=db,
            mark_seen=False,
        )
        if force_generate or len(bank_questions) < candidate_count:
            generated = await QuizService._generate_and_store_question_candidates(
                chapter_id,
                count=bank_generation_count,
                quiz_mode=mode,
                question_type=question_type,
                personalization_context=None,
                previous_questions=[
                    *(previous_questions or []),
                    *(question.question_text for question in bank_questions),
                ],
                db=db,
            )
            if force_generate:
                selected_generated = generated[:candidate_count]
                now = datetime.utcnow()
                for question in selected_generated:
                    question.times_seen = int(question.times_seen or 0) + 1
                    question.last_seen_at = now
                await db.commit()
                for question in selected_generated:
                    await db.refresh(question)
                return selected_generated

        return await QuizService.choose_candidates_from_bank(
            book_id=book.id,
            chapter_id=chapter.id,
            question_type=question_type,
            quiz_mode=mode,
            count=candidate_count,
            previous_questions=previous_questions,
            db=db,
            mark_seen=True,
        )

    @staticmethod
    async def choose_from_bank(
        *,
        book_id: int,
        chapter_id: int | None,
        question_type: str | None,
        quiz_mode: str,
        db: AsyncSession,
    ) -> QuizQuestion | None:
        mode = normalize_quiz_mode(quiz_mode)
        query = select(QuizQuestion).where(QuizQuestion.book_id == book_id)
        if chapter_id is None:
            query = query.where(QuizQuestion.chapter_id.is_(None))
        else:
            query = query.where(QuizQuestion.chapter_id == chapter_id)
        query = query.where(QuizQuestion.quiz_mode == mode)
        if question_type:
            query = query.where(QuizQuestion.question_type == canonical_question_type(question_type))
        result = await db.execute(
            query.order_by(
                QuizQuestion.attempts_count.asc(),
                QuizQuestion.times_seen.asc(),
                QuizQuestion.created_at.asc(),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def chapter_bank_count(*, book_id: int, chapter_id: int, db: AsyncSession) -> int:
        result = await db.execute(
            select(func.count(QuizQuestion.id)).where(
                QuizQuestion.book_id == book_id,
                QuizQuestion.chapter_id == chapter_id,
                QuizQuestion.quiz_mode == CHAPTER_QUIZ_MODE,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def generate_sparse_chapter_bank(
        *,
        book: Book,
        chapter: Chapter,
        selected_type: str,
        db: AsyncSession,
    ) -> list[QuizQuestion]:
        generated: list[QuizQuestion] = []
        for question_type in QuizService.sparse_bank_question_types(selected_type):
            existing = await QuizService.choose_from_bank(
                book_id=book.id,
                chapter_id=chapter.id,
                question_type=question_type,
                quiz_mode=CHAPTER_QUIZ_MODE,
                db=db,
            )
            if existing:
                continue
            try:
                generated.append(
                    await QuizService.generate_question(
                        book=book,
                        chapter=chapter,
                        question_type=question_type,
                        quiz_mode=CHAPTER_QUIZ_MODE,
                        db=db,
                        source="runtime_batch",
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Sparse quiz bank generation failed book=%s chapter=%s type=%s error=%s",
                    book.id,
                    chapter.id,
                    question_type,
                    exc,
                )
        return generated

    @staticmethod
    async def next_chapter_question(
        chapter_id: int,
        *,
        quiz_mode: str,
        question_type: str | None,
        personalization_context: str | None,
        db: AsyncSession,
    ) -> QuizQuestion | None:
        mode = normalize_quiz_mode(quiz_mode)
        chapter = await QuizService._chapter_or_none(chapter_id, db)
        if not chapter:
            return None
        if question_type and not is_valid_question_type(question_type):
            raise ValueError(f"Unsupported quiz question type: {question_type}")
        selected_type = (
            canonical_question_type(question_type)
            if question_type
            else QuizService.weighted_random_question_type()
        )
        book = await QuizService._book_or_none(chapter.book_id, db)
        if not book:
            return None

        if mode == BOOK_QUIZ_MODE:
            question = await QuizService.generate_question(
                book=book,
                chapter=chapter,
                question_type=selected_type,
                quiz_mode=mode,
                db=db,
                source="book_adaptive",
                personalization_context=personalization_context,
            )
        else:
            question = None
            bank_count = await QuizService.chapter_bank_count(
                book_id=chapter.book_id,
                chapter_id=chapter.id,
                db=db,
            )
            if bank_count < QuizService.CHAPTER_BANK_SPARSE_THRESHOLD:
                generated = await QuizService.generate_sparse_chapter_bank(
                    book=book,
                    chapter=chapter,
                    selected_type=selected_type,
                    db=db,
                )
                question = next((item for item in generated if item.question_type == selected_type), None)
                if question is None:
                    question = await QuizService.choose_from_bank(
                        book_id=chapter.book_id,
                        chapter_id=chapter.id,
                        question_type=selected_type,
                        quiz_mode=mode,
                        db=db,
                    )
                if question is None and not question_type:
                    question = generated[0] if generated else None
            if question is None:
                question = await QuizService.choose_from_bank(
                    book_id=chapter.book_id,
                    chapter_id=chapter.id,
                    question_type=question_type or selected_type,
                    quiz_mode=mode,
                    db=db,
                )
        if question is None:
            question = await QuizService.generate_question(
                book=book,
                chapter=chapter,
                question_type=selected_type,
                quiz_mode=mode,
                db=db,
                source="runtime",
                personalization_context=personalization_context,
            )
        question.times_seen = int(question.times_seen or 0) + 1
        question.last_seen_at = datetime.utcnow()
        await db.commit()
        await db.refresh(question)
        return question

    @staticmethod
    def _default_followup_question(question: QuizQuestion) -> str:
        skill = get_quiz_skill(question.question_type)
        fallback_followups = {
            "concept_explain": "请再挑一个你认为最关键的性质，说明缺少它会发生什么。",
            "theorem_understanding": "请再选一个关键条件，说明它在结论中起什么作用。",
            "proof_strategy": "请再说明证明中最关键的转折，以及这一步为什么能推进到结论。",
            "concept_connection": "请再说清两者关系的方向：哪一边依赖或服务于哪一边？",
        }
        return fallback_followups[skill.question_type]

    @staticmethod
    def _local_evaluation(question: QuizQuestion, answer_text: str) -> dict[str, Any]:
        return {
            "evaluation_status": "partial",
            "score": 0.5,
            "missing_points": [],
            "feedback_text": (
                "已记录你的讲解。当前没有可用的模型，系统无法仅凭关键词可靠判断数学含义，"
                "因此暂不把这次回答判成正确或错误。"
            ),
            "followup_text": QuizService._default_followup_question(question),
        }

    @staticmethod
    def normalize_evaluation(data: dict[str, Any], question: QuizQuestion, answer_text: str) -> dict[str, Any]:
        status = str(data.get("evaluation_status") or data.get("status") or "").strip().lower()
        if status not in {"completed", "partial", "wrong"}:
            return QuizService._local_evaluation(question, answer_text)
        missing_points = data.get("missing_points") or []
        if isinstance(missing_points, str):
            missing_points = [missing_points]
        score = data.get("score")
        try:
            score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            score = {"completed": 1.0, "partial": 0.55, "wrong": 0.0}[status]
        fallback_feedback = {
            "completed": "你的讲解已经覆盖了这道题的核心逻辑。",
            "partial": "你的讲解方向基本正确，但还有一个关键连接需要说清。",
            "wrong": "当前讲解的核心方向需要重新检查，请先从题目中的对象和条件开始。",
        }
        return {
            "evaluation_status": status,
            "score": score,
            "missing_points": [str(point) for point in missing_points if str(point).strip()],
            "feedback_text": str(
                data.get("feedback_text") or data.get("feedback") or fallback_feedback[status]
            ),
            "followup_text": str(
                data.get("followup_text")
                or data.get("followup")
                or QuizService._default_followup_question(question)
            ),
        }

    @staticmethod
    async def submit_attempt(
        question_id: int,
        answer_text: str,
        db: AsyncSession,
        *,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        result = await db.execute(select(QuizQuestion).where(QuizQuestion.id == question_id))
        question = result.scalar_one_or_none()
        if not question:
            return None

        translator = TranslatorService(task="quiz")
        evaluation = None
        if getattr(translator, "api_key", None):
            skill = get_quiz_skill(question.question_type)
            system_prompt = (
                "You are a Feynman-style mathematics coach evaluating a learner's teach-back explanation. "
                "Judge mathematical meaning, not keyword overlap or notation. Accept clear everyday language, analogies, "
                "and omitted algebraic detail when the reasoning is sound. Never penalize the learner for not typing formulas. "
                "Use the full conversation history when a later answer is responding to your earlier follow-up. "
                "Be demanding about reversed implications, missing hypotheses, circular proof plans, and misleading analogies. "
                "Write feedback in concise Chinese: first name one thing the learner understood, then identify at most one "
                "most important gap or correction. Ask exactly one short follow-up that helps the learner repair the explanation; "
                "do not dump the full standard answer. Return strictly valid JSON with keys: "
                "evaluation_status (completed|partial|wrong), score, missing_points, feedback_text, followup_text. "
                "Use completed only when the core explanation is genuinely sound, partial when the main direction is right "
                "but one important link is missing, and wrong when the central idea or logical direction is incorrect."
            )
            user_prompt = json.dumps(
                {
                    "quiz_mode": normalize_quiz_mode(getattr(question, "quiz_mode", None)),
                    "question_text": question.question_text,
                    "question_type": question.question_type,
                    "question_type_label": skill.label,
                    "type_specific_evaluation": skill.evaluation_prompt,
                    "answer_guidance": skill.answer_guidance,
                    "expected_points": question.expected_points or [],
                    "common_mistakes": question.common_mistakes or [],
                    "evaluation_rubric": question.evaluation_rubric or {},
                    "followup_strategy": question.followup_strategy or "",
                    "conversation_history": conversation_history or [],
                    "answer_text": answer_text,
                },
                ensure_ascii=False,
                indent=2,
            )
            try:
                raw = await translator.complete(user_prompt, system_prompt, temperature=0.2)
                parsed = extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))
                evaluation = QuizService.normalize_evaluation(parsed, question, answer_text)
            except Exception as exc:
                logger.warning("Quiz answer evaluation failed: %s", exc)

        if evaluation is None:
            evaluation = QuizService._local_evaluation(question, answer_text)

        attempt = QuizAttempt(
            question_id=question.id,
            book_id=question.book_id,
            chapter_id=question.chapter_id,
            answer_text=answer_text,
            **evaluation,
        )
        db.add(attempt)
        question.attempts_count = int(question.attempts_count or 0) + 1
        if evaluation["evaluation_status"] == "completed":
            question.correct_count = int(question.correct_count or 0) + 1
        elif evaluation["evaluation_status"] == "partial":
            question.partial_count = int(question.partial_count or 0) + 1
        else:
            question.wrong_count = int(question.wrong_count or 0) + 1
        await db.commit()
        await db.refresh(attempt)
        return {
            "id": attempt.id,
            "question_id": question.id,
            "book_id": question.book_id,
            "chapter_id": question.chapter_id,
            **evaluation,
            "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
        }

    @staticmethod
    async def select_target(book_id: int, personalization_context: str | None, db: AsyncSession) -> dict[str, Any] | None:
        book = await QuizService._book_or_none(book_id, db)
        if not book:
            return None
        chapters_result = await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.order))
        chapters = list(chapters_result.scalars().all())
        if not chapters:
            return None

        profile = await LearningProfileService.read_profile(book.uuid)
        attempts_result = await db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.book_id == book_id)
            .order_by(QuizAttempt.created_at.desc())
            .limit(20)
        )
        attempts = list(attempts_result.scalars().all())
        chapter_by_id = {chapter.id: chapter for chapter in chapters}

        weak_counts: dict[int, int] = {}
        for attempt in attempts:
            if attempt.chapter_id and attempt.evaluation_status in {"partial", "wrong"}:
                weak_counts[attempt.chapter_id] = weak_counts.get(attempt.chapter_id, 0) + 1
        selected_chapter = chapter_by_id.get(max(weak_counts, key=weak_counts.get)) if weak_counts else chapters[0]
        selected_type = "theorem_understanding" if weak_counts else "concept_explain"

        translator = TranslatorService(task="quiz")
        if getattr(translator, "api_key", None):
            system_prompt = (
                "Select the next Book Quiz target for a mathematics reader. This layer chooses what the learner should "
                "teach back; it does not write the question. Prefer a specific weak or not-yet-explained concept supported "
                "by the learning profile and recent attempts. Choose proof_strategy only when the chapter actually contains "
                "a proof worth explaining, and theorem_understanding only for a named theorem or key result. "
                "Return strictly valid JSON with "
                "chapter_id, question_type, target_concept, reason. chapter_id must be one of the provided ids; "
                f"question_type must be one of: {', '.join(QUIZ_SKILLS)}."
            )
            user_prompt = json.dumps(
                {
                    "book": {"id": book.id, "title": book.title},
                    "chapters": [
                        {
                            "id": chapter.id,
                            "chapter_index": chapter.chapter_index,
                            "title": chapter.title_zh or chapter.title_en,
                        }
                        for chapter in chapters
                    ],
                    "user_profile": profile,
                    "recent_attempts": [
                        {
                            "chapter_id": attempt.chapter_id,
                            "status": attempt.evaluation_status,
                            "missing_points": attempt.missing_points or [],
                        }
                        for attempt in attempts[:12]
                    ],
                    "personalization_context": personalization_context or "",
                },
                ensure_ascii=False,
                indent=2,
            )
            try:
                raw = await translator.complete(user_prompt, system_prompt, temperature=0.2)
                parsed = extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))
                parsed_chapter_id = int(parsed.get("chapter_id"))
                parsed_type = str(parsed.get("question_type") or "")
                if parsed_chapter_id in chapter_by_id and is_valid_question_type(parsed_type):
                    selected_chapter = chapter_by_id[parsed_chapter_id]
                    selected_type = parsed_type
                    target_concept = str(parsed.get("target_concept") or "")
                    reason = str(parsed.get("reason") or "")
                    return {
                        "chapter_id": selected_chapter.id,
                        "chapter_index": selected_chapter.chapter_index,
                        "chapter_title": selected_chapter.title_zh or selected_chapter.title_en or "",
                        "question_type": selected_type,
                        "target_concept": target_concept,
                        "reason": reason or "Selected from current learning profile and recent quiz attempts.",
                    }
            except Exception as exc:
                logger.warning("Book quiz target selection failed: %s", exc)

        return {
            "chapter_id": selected_chapter.id,
            "chapter_index": selected_chapter.chapter_index,
            "chapter_title": selected_chapter.title_zh or selected_chapter.title_en or "",
            "question_type": selected_type,
            "target_concept": selected_chapter.title_zh or selected_chapter.title_en or "",
            "reason": (
                f"Target concept: {selected_chapter.title_zh or selected_chapter.title_en or ''}. "
                "Selected by local fallback from recent partial/wrong attempts and chapter order."
            ),
        }
