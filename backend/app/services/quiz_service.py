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


class QuizService:
    CHAPTER_BANK_SPARSE_THRESHOLD = 3
    CHAPTER_BANK_BATCH_SIZE = 3

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
            if len(ordered) >= QuizService.CHAPTER_BANK_BATCH_SIZE:
                break
        return ordered

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
    ) -> str:
        skill = get_quiz_skill(question_type)
        mode = normalize_quiz_mode(quiz_mode)
        mode_goal = (
            "This is a Book Quiz: diagnose the learner's selected weak point in the book. "
            "Use the personalization context as a targeting instruction, but do not reveal private profile evidence in the question."
            if mode == BOOK_QUIZ_MODE
            else (
                "This is a Chapter Quiz: ask one focused teach-back question about the current chapter. "
                "The chapter body is authoritative; guides only provide structural orientation."
            )
        )
        parts = [
            f"Book: {book.title}",
            f"Quiz mode: {mode}",
            f"Mode goal: {mode_goal}",
            f"Question type: {skill.question_type}",
            f"Goal: {skill.goal}",
            f"Required context: {', '.join(skill.required_context)}",
            f"Type-specific generation instruction: {skill.generation_prompt}",
            f"How the learner should answer: {skill.answer_guidance}",
        ]
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
                    "Chapter guide:",
                    await QuizService._chapter_guide_text(book.uuid, chapter.chapter_index),
                ]
            )
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
            question_text = f"请围绕本章完成一次「{skill.label}」：{skill.answer_guidance}"
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
    def _fallback_question_data(
        *,
        book_id: int,
        chapter_id: int | None,
        chapter_title: str,
        question_type: str,
        quiz_mode: str,
        source: str,
        personalization_context: str | None = None,
    ) -> dict[str, Any]:
        skill = get_quiz_skill(question_type)
        personalization_hint = str(personalization_context or "").strip()
        target_concept = next(
            (
                line.split(":", 1)[1].strip()
                for line in personalization_hint.splitlines()
                if line.lower().startswith("target concept:") and ":" in line
            ),
            "",
        )
        target_hint = f"，重点围绕「{target_concept}」" if target_concept else ""
        fallback_questions = {
            "concept_explain": (
                f"假设你要向刚读到「{chapter_title or '本章'}」的同学讲解其中最核心的一个概念{target_hint}。"
                "它描述什么、最关键的性质是什么？请再用一个例子或直观后果帮助对方理解。"
            ),
            "theorem_understanding": (
                f"请选择「{chapter_title or '本章'}」中的一个关键定理或结论{target_hint}，用自己的话说明："
                "它需要哪些关键条件、保证了什么，以及其中一个条件为什么不能随便删掉。"
            ),
            "proof_strategy": (
                f"请选择「{chapter_title or '本章'}」中的一个重要证明{target_hint}，像口头讲解一样说出证明路线："
                "从哪里出发，关键转折是什么，它怎样把问题推进到结论？不用写完整公式推导。"
            ),
            "concept_connection": (
                f"请选择「{chapter_title or '本章'}」中两个有直接联系的概念或结果{target_hint}。"
                "请分别说明它们的角色，再解释两者怎样连接、为什么要放在一起理解。"
            ),
        }
        question_text = fallback_questions[skill.question_type]
        data = {
            "question_text": question_text,
            "target_concepts": [item for item in [chapter_title, target_concept] if item],
            "expected_points": list(skill.expected_points),
            "common_mistakes": [
                "只重复书中的结论，没有解释为什么",
                "堆砌术语或公式，却没有讲清逻辑关系",
            ],
        }
        return QuizService.normalize_question_data(
            data,
            book_id=book_id,
            chapter_id=chapter_id,
            question_type=question_type,
            quiz_mode=quiz_mode,
            source=source,
        )

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
        normalized: dict[str, Any] | None = None
        if getattr(translator, "api_key", None):
            system_prompt = (
                "You design one Feynman-style teach-back question for a reader of a serious mathematics book. "
                "The learner must be able to answer in ordinary natural language, typically in 2-6 sentences. "
                "Never require typing a formula, carrying out a calculation, filling a missing equation, reproducing notation, "
                "or writing a complete formal proof. You may ask what an existing formula means or how a proof works. "
                "Use only claims actually supported by the supplied source. Ask one question with one coherent learning target, "
                "write the question in Chinese, and do not include the answer or expose learning-profile evidence. "
                "Return strictly valid JSON with keys: "
                "question_text, difficulty, target_concepts, expected_points, common_mistakes, context_refs, "
                "evaluation_rubric, followup_strategy. expected_points must describe semantic ideas, not exact keywords. "
                "context_refs must identify the source section or named result that supports the question. "
                "When personalization context is provided, target that concept or weakness without mentioning the profile itself."
            )
            user_prompt = (
                f"{context}\n\n"
                f"Generate exactly one {skill.label} ({skill.question_type}) question.\n"
                f"Type-specific instruction: {skill.generation_prompt}\n"
                f"Evaluation focus: {skill.evaluation_prompt}\n"
                f"Default semantic answer points: {json.dumps(skill.expected_points, ensure_ascii=False)}\n"
                f"Default rubric: {json.dumps(skill.evaluation_rubric, ensure_ascii=False)}\n"
                f"Follow-up rule: {skill.next_step_rule}"
            )
            try:
                raw = await translator.complete(user_prompt, system_prompt, temperature=0.4)
                parsed = extract_json_candidate(raw, validator=lambda value: isinstance(value, dict))
                normalized = QuizService.normalize_question_data(
                    parsed,
                    book_id=book.id,
                    chapter_id=chapter.id if chapter else None,
                    question_type=skill.question_type,
                    quiz_mode=mode,
                    source=source,
                )
            except Exception as exc:
                logger.warning("Quiz question generation failed: %s", exc)

        if normalized is None:
            normalized = QuizService._fallback_question_data(
                book_id=book.id,
                chapter_id=chapter.id if chapter else None,
                chapter_title=chapter.title_zh or chapter.title_en or chapter.chapter_index if chapter else book.title,
                question_type=skill.question_type,
                quiz_mode=mode,
                source=source,
                personalization_context=personalization_context,
            )

        question = QuizQuestion(**normalized)
        db.add(question)
        await db.commit()
        await db.refresh(question)
        return question

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
    ) -> list[QuizQuestion] | None:
        """Generate a small, distinct candidate pool in one LLM call."""
        mode = normalize_quiz_mode(quiz_mode)
        candidate_count = max(1, min(QuizService.CHAPTER_BANK_BATCH_SIZE, int(count or 1)))
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
            selected_types = QuizService.sparse_bank_question_types(
                QuizService.weighted_random_question_type()
            )[:candidate_count]

        context = await QuizService.build_generation_context(
            book,
            chapter,
            selected_types[0],
            mode,
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
                    "default_rubric": skill.evaluation_rubric,
                    "followup_rule": skill.next_step_rule,
                }
            )

        translator = TranslatorService(task="quiz")
        parsed_questions: list[dict[str, Any]] = []
        if getattr(translator, "api_key", None):
            system_prompt = (
                "You design a small set of distinct Feynman-style teach-back questions for a reader of a serious "
                "mathematics book. Every question must be answerable in ordinary natural language, typically in 2-6 "
                "sentences. Never require typing a formula, carrying out a calculation, filling a missing equation, "
                "reproducing notation, or writing a complete formal proof. Use only claims supported by the supplied "
                "source. Write in Chinese and do not include answers or expose learning-profile evidence. The questions "
                "must test meaningfully different concepts, results, proof turns, or connections. Do not repeat or lightly "
                "paraphrase any previous question. Return strictly valid JSON as {\"questions\": [...]}. Each item must "
                "contain question_type, question_text, difficulty, target_concepts, expected_points, common_mistakes, "
                "context_refs, evaluation_rubric, and followup_strategy."
            )
            user_prompt = (
                f"{context}\n\n"
                f"Generate exactly {candidate_count} candidate questions.\n"
                f"Candidate specifications, in order:\n{json.dumps(type_specs, ensure_ascii=False)}\n\n"
                f"Previous questions that must not be repeated or lightly paraphrased:\n"
                f"{json.dumps(old_questions, ensure_ascii=False)}"
            )
            try:
                raw = await translator.complete(user_prompt, system_prompt, temperature=0.55)
                parsed = extract_json_candidate(
                    raw,
                    validator=lambda value: (
                        isinstance(value, dict) and isinstance(value.get("questions"), list)
                    ),
                )
                parsed_questions = [item for item in parsed["questions"] if isinstance(item, dict)]
            except Exception as exc:
                logger.warning("Quiz candidate generation failed: %s", exc)

        normalized_questions: list[dict[str, Any]] = []
        seen_texts = {text.casefold() for text in old_questions}
        chapter_title = chapter.title_zh or chapter.title_en or chapter.chapter_index
        for index, candidate_type in enumerate(selected_types):
            raw_data = parsed_questions[index] if index < len(parsed_questions) else {}
            normalized = QuizService.normalize_question_data(
                raw_data,
                book_id=book.id,
                chapter_id=chapter.id,
                question_type=candidate_type,
                quiz_mode=mode,
                source="book_candidate_batch" if mode == BOOK_QUIZ_MODE else "chapter_candidate_batch",
            ) if raw_data else QuizService._fallback_question_data(
                book_id=book.id,
                chapter_id=chapter.id,
                chapter_title=chapter_title,
                question_type=candidate_type,
                quiz_mode=mode,
                source="book_candidate_fallback" if mode == BOOK_QUIZ_MODE else "chapter_candidate_fallback",
                personalization_context=personalization_context,
            )
            normalized_key = " ".join(normalized["question_text"].split()).casefold()
            if normalized_key in seen_texts and raw_data:
                normalized = QuizService._fallback_question_data(
                    book_id=book.id,
                    chapter_id=chapter.id,
                    chapter_title=chapter_title,
                    question_type=candidate_type,
                    quiz_mode=mode,
                    source="book_candidate_fallback" if mode == BOOK_QUIZ_MODE else "chapter_candidate_fallback",
                    personalization_context=personalization_context,
                )
                normalized_key = " ".join(normalized["question_text"].split()).casefold()
            seen_texts.add(normalized_key)
            normalized_questions.append(normalized)

        questions = [QuizQuestion(**data, times_seen=1, last_seen_at=datetime.utcnow()) for data in normalized_questions]
        for question in questions:
            db.add(question)
        await db.commit()
        for question in questions:
            await db.refresh(question)
        return questions

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
