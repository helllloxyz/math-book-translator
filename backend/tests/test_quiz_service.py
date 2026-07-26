from types import SimpleNamespace

import pytest

from app.models.schema import QuizQuestion
from app.services.book_storage import BookStorage
from app.services.quiz_service import QuizService
from app.services.quiz_skill_registry import QUIZ_SKILLS, question_type_weights


def test_quiz_skill_registry_has_fixed_supported_types():
    assert set(QUIZ_SKILLS) == {
        "concept_explain",
        "concept_relation",
        "reasoning_fill",
        "condition_boundary",
        "application",
        "compare",
        "global_structure",
    }
    assert all(weight > 0 for weight in question_type_weights().values())


def test_weighted_random_question_type_uses_registry_weights(monkeypatch):
    monkeypatch.setattr("app.services.quiz_service.random.random", lambda: 0)
    assert QuizService.weighted_random_question_type() == "concept_explain"

    monkeypatch.setattr("app.services.quiz_service.random.random", lambda: 0.999)
    assert QuizService.weighted_random_question_type() == "global_structure"


def test_sparse_bank_question_types_start_with_selected_type():
    question_types = QuizService.sparse_bank_question_types("application")

    assert question_types[0] == "application"
    assert len(question_types) == QuizService.CHAPTER_BANK_BATCH_SIZE
    assert len(set(question_types)) == len(question_types)


def test_personalized_fallback_question_uses_context():
    normalized = QuizService._fallback_question_data(
        book_id=1,
        chapter_id=2,
        chapter_title="Vector Spaces",
        question_type="concept_explain",
        source="personalized",
        personalization_context="Target concept: basis",
    )

    assert normalized["source"] == "personalized"
    assert "Target concept: basis" in normalized["question_text"]
    assert "Target concept: basis" in normalized["target_concepts"]


def test_quiz_question_normalization_uses_registered_rubric():
    normalized = QuizService.normalize_question_data(
        {
            "question": "What condition is needed?",
            "target_concepts": "Compactness",
            "expected_points": "Name the hypothesis",
        },
        book_id=1,
        chapter_id=2,
        question_type="condition_boundary",
        source="runtime",
    )

    assert normalized["question_type"] == "condition_boundary"
    assert normalized["target_concepts"] == ["Compactness"]
    assert normalized["expected_points"] == ["Name the hypothesis"]
    assert "completed" in normalized["evaluation_rubric"]


def test_local_quiz_evaluation_returns_valid_status():
    question = QuizQuestion(
        id=1,
        book_id=1,
        chapter_id=2,
        question_type="concept_explain",
        question_text="Explain vector spaces.",
        expected_points=["closed under addition", "closed under scalar multiplication"],
        followup_strategy="Name one missing axiom.",
    )

    evaluation = QuizService._local_evaluation(question, "A vector space is closed under addition.")

    assert evaluation["evaluation_status"] in {"completed", "partial", "wrong"}
    assert isinstance(evaluation["missing_points"], list)
    assert evaluation["followup_text"] == "Name one missing axiom."


@pytest.mark.asyncio
async def test_personalized_chapter_question_bypasses_generic_bank(monkeypatch):
    chapter = SimpleNamespace(
        id=2,
        book_id=1,
        chapter_index="1",
        title_en="Vector Spaces",
        title_zh=None,
    )
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Linear Algebra")
    calls = []

    async def chapter_or_none(chapter_id, db):
        return chapter

    async def book_or_none(book_id, db):
        return book

    async def choose_from_bank(**kwargs):
        raise AssertionError(
            "personalized questions must not be short-circuited by generic bank questions"
        )

    async def generate_question(**kwargs):
        calls.append(kwargs)
        return QuizQuestion(
            id=10,
            book_id=1,
            chapter_id=2,
            source=kwargs["source"],
            question_type=kwargs["question_type"],
            question_text="Use the learner's target concept to explain vector spaces.",
        )

    monkeypatch.setattr(QuizService, "_chapter_or_none", chapter_or_none)
    monkeypatch.setattr(QuizService, "_book_or_none", book_or_none)
    monkeypatch.setattr(QuizService, "choose_from_bank", choose_from_bank)
    monkeypatch.setattr(QuizService, "generate_question", generate_question)

    async def commit():
        pass

    async def refresh(obj):
        pass

    db = SimpleNamespace(commit=commit, refresh=refresh)

    question = await QuizService.next_chapter_question(
        2,
        question_type="condition_boundary",
        personalization_context="Target concept: basis. Focus on weak prior attempts.",
        db=db,
    )

    assert question.source == "personalized"
    assert calls[0]["personalization_context"] == "Target concept: basis. Focus on weak prior attempts."


@pytest.mark.asyncio
async def test_sparse_chapter_bank_generates_batch_and_returns_selected(monkeypatch):
    chapter = SimpleNamespace(
        id=2,
        book_id=1,
        chapter_index="1",
        title_en="Vector Spaces",
        title_zh=None,
    )
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Linear Algebra")
    generated_types = []

    async def chapter_or_none(chapter_id, db):
        return chapter

    async def book_or_none(book_id, db):
        return book

    async def chapter_bank_count(**kwargs):
        return 0

    async def choose_from_bank(**kwargs):
        return None

    async def generate_question(**kwargs):
        generated_types.append(kwargs["question_type"])
        return QuizQuestion(
            id=10 + len(generated_types),
            book_id=1,
            chapter_id=2,
            source=kwargs["source"],
            question_type=kwargs["question_type"],
            question_text=f"{kwargs['question_type']} question",
        )

    monkeypatch.setattr(QuizService, "_chapter_or_none", chapter_or_none)
    monkeypatch.setattr(QuizService, "_book_or_none", book_or_none)
    monkeypatch.setattr(QuizService, "chapter_bank_count", chapter_bank_count)
    monkeypatch.setattr(QuizService, "choose_from_bank", choose_from_bank)
    monkeypatch.setattr(QuizService, "generate_question", generate_question)
    monkeypatch.setattr(QuizService, "weighted_random_question_type", lambda: "application")

    async def commit():
        pass

    async def refresh(obj):
        pass

    db = SimpleNamespace(commit=commit, refresh=refresh)

    question = await QuizService.next_chapter_question(
        2,
        question_type=None,
        personalization_context=None,
        db=db,
    )

    assert question.question_type == "application"
    assert question.source == "runtime_batch"
    assert generated_types == QuizService.sparse_bank_question_types("application")


def test_learning_profile_storage_paths_use_book_user_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    assert BookStorage.user_profile_path("book-uuid") == tmp_path / "book-uuid" / "book_user" / "User.md"
    assert BookStorage.user_profile_meta_path("book-uuid") == tmp_path / "book-uuid" / "book_user" / "profile_meta.json"

    BookStorage.ensure_book_dirs("book-uuid")
    assert (tmp_path / "book-uuid" / "book_user").is_dir()
