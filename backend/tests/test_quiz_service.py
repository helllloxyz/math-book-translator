import json
from types import SimpleNamespace

import pytest

from app.models.schema import QuizQuestion
from app.services.book_storage import BookStorage
from app.services.quiz_service import QuizService
from app.services.quiz_skill_registry import QUIZ_SKILLS, question_type_weights


def test_quiz_skill_registry_has_fixed_supported_types():
    assert set(QUIZ_SKILLS) == {
        "concept_explain",
        "theorem_understanding",
        "proof_strategy",
        "concept_connection",
    }
    assert all(weight > 0 for weight in question_type_weights().values())
    assert all("公式" in skill.answer_guidance or "formula" in skill.answer_guidance.lower() for skill in QUIZ_SKILLS.values())
    assert len({skill.generation_prompt for skill in QUIZ_SKILLS.values()}) == len(QUIZ_SKILLS)


def test_weighted_random_question_type_uses_registry_weights(monkeypatch):
    monkeypatch.setattr("app.services.quiz_service.random.random", lambda: 0)
    assert QuizService.weighted_random_question_type() == "concept_explain"

    monkeypatch.setattr("app.services.quiz_service.random.random", lambda: 0.999)
    assert QuizService.weighted_random_question_type() == "concept_connection"


def test_sparse_bank_question_types_start_with_selected_type():
    question_types = QuizService.sparse_bank_question_types("proof_strategy")

    assert question_types[0] == "proof_strategy"
    assert len(question_types) == QuizService.CHAPTER_BANK_BATCH_SIZE
    assert len(set(question_types)) == len(question_types)


def test_personalized_fallback_question_uses_context():
    normalized = QuizService._fallback_question_data(
        book_id=1,
        chapter_id=2,
        chapter_title="Vector Spaces",
        question_type="concept_explain",
        quiz_mode="book",
        source="book_adaptive",
        personalization_context="Target concept: basis",
    )

    assert normalized["source"] == "book_adaptive"
    assert normalized["quiz_mode"] == "book"
    assert "basis" in normalized["question_text"]
    assert "basis" in normalized["target_concepts"]
    assert "Target concept:" not in normalized["question_text"]


def test_quiz_question_normalization_uses_registered_rubric():
    normalized = QuizService.normalize_question_data(
        {
            "question": "What condition is needed?",
            "target_concepts": "Compactness",
            "expected_points": "Name the hypothesis",
        },
        book_id=1,
        chapter_id=2,
        question_type="theorem_understanding",
        quiz_mode="chapter",
        source="runtime",
    )

    assert normalized["question_type"] == "theorem_understanding"
    assert normalized["target_concepts"] == ["Compactness"]
    assert normalized["expected_points"] == ["Name the hypothesis"]
    assert "completed" in normalized["evaluation_rubric"]


def test_quiz_question_response_exposes_mode_type_label_and_natural_answer_guidance():
    question = QuizQuestion(
        id=3,
        book_id=1,
        chapter_id=2,
        quiz_mode="book",
        source="book_adaptive",
        question_type="proof_strategy",
        difficulty="medium",
        question_text="请讲解证明路线。",
    )

    payload = QuizService.question_to_dict(question)

    assert payload["quiz_mode"] == "book"
    assert payload["question_type_label"] == "证明思路"
    assert "不必补公式" in payload["answer_guidance"]


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
    assert evaluation["followup_text"] == "请再挑一个你认为最关键的性质，说明缺少它会发生什么。"


def test_local_quiz_evaluation_does_not_guess_correctness_from_keywords():
    question = QuizQuestion(
        id=1,
        book_id=1,
        chapter_id=2,
        question_type="concept_explain",
        question_text="Explain vector spaces.",
        expected_points=["closed under addition"],
    )

    evaluation = QuizService._local_evaluation(
        question,
        "closed under addition closed under addition closed under addition",
    )

    assert evaluation["evaluation_status"] == "partial"
    assert "无法仅凭关键词" in evaluation["feedback_text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("question_type", ["concept_explain", "theorem_understanding", "proof_strategy", "concept_connection"])
async def test_question_generation_uses_feynman_and_type_specific_prompts(monkeypatch, question_type):
    calls = []

    class FakeTranslator:
        api_key = "configured"

        def __init__(self, **_kwargs):
            pass

        async def complete(self, user_prompt, system_prompt, temperature):
            calls.append((user_prompt, system_prompt, temperature))
            return '{"question_text":"请用自己的话讲解。","expected_points":["讲清关键联系"]}'

    async def context(*_args, **_kwargs):
        return "SOURCE BODY"

    class FakeDb:
        def add(self, _value):
            pass

        async def commit(self):
            pass

        async def refresh(self, _value):
            pass

    monkeypatch.setattr("app.services.quiz_service.TranslatorService", FakeTranslator)
    monkeypatch.setattr(QuizService, "build_generation_context", context)
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Book")
    chapter = SimpleNamespace(id=2, chapter_index="1", title_zh="本章", title_en=None)

    question = await QuizService.generate_question(
        book=book,
        chapter=chapter,
        question_type=question_type,
        quiz_mode="chapter",
        db=FakeDb(),
    )

    user_prompt, system_prompt, _temperature = calls[0]
    assert QUIZ_SKILLS[question_type].generation_prompt in user_prompt
    assert QUIZ_SKILLS[question_type].evaluation_prompt in user_prompt
    assert "Never require typing a formula" in system_prompt
    assert "ordinary natural language" in system_prompt
    assert question.question_type == question_type
    assert question.quiz_mode == "chapter"


@pytest.mark.asyncio
async def test_attempt_evaluation_uses_conversation_history_and_semantic_type_focus(monkeypatch):
    calls = []
    question = QuizQuestion(
        id=9,
        book_id=1,
        chapter_id=2,
        quiz_mode="book",
        question_type="proof_strategy",
        question_text="请讲解这个证明的路线。",
        expected_points=["先构造局部对象", "再用紧致性取得有限覆盖"],
        common_mistakes=["只复述结论"],
        evaluation_rubric=QUIZ_SKILLS["proof_strategy"].evaluation_rubric,
        followup_strategy=QUIZ_SKILLS["proof_strategy"].next_step_rule,
        attempts_count=0,
        correct_count=0,
        partial_count=0,
        wrong_count=0,
    )

    class FakeTranslator:
        api_key = "configured"

        def __init__(self, **_kwargs):
            pass

        async def complete(self, user_prompt, system_prompt, temperature):
            calls.append((json.loads(user_prompt), system_prompt, temperature))
            return (
                '{"evaluation_status":"partial","score":0.6,'
                '"missing_points":["有限子覆盖的作用"],'
                '"feedback_text":"你已经说清了构造的起点。",'
                '"followup_text":"有限子覆盖在这里解决了什么问题？"}'
            )

    class Result:
        def scalar_one_or_none(self):
            return question

    class FakeDb:
        async def execute(self, _query):
            return Result()

        def add(self, _value):
            pass

        async def commit(self):
            pass

        async def refresh(self, _value):
            pass

    monkeypatch.setattr("app.services.quiz_service.TranslatorService", FakeTranslator)
    history = [
        {"role": "assistant", "content": question.question_text},
        {"role": "user", "content": "先构造局部对象。"},
        {"role": "assistant", "content": "还需要什么把局部结果合起来？"},
        {"role": "user", "content": "再利用紧致性取有限子覆盖。"},
    ]

    result = await QuizService.submit_attempt(
        9,
        "再利用紧致性取有限子覆盖。",
        FakeDb(),
        conversation_history=history,
    )

    payload, system_prompt, _temperature = calls[0]
    assert payload["conversation_history"] == history
    assert payload["type_specific_evaluation"] == QUIZ_SKILLS["proof_strategy"].evaluation_prompt
    assert "Never penalize the learner for not typing formulas" in system_prompt
    assert result["evaluation_status"] == "partial"
    assert result["followup_text"] == "有限子覆盖在这里解决了什么问题？"


@pytest.mark.asyncio
async def test_quiz_generation_context_reads_direct_chapter_body(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    chapter = SimpleNamespace(
        id=2,
        book_id=1,
        chapter_index="1",
        title_en="Vector Spaces",
        title_zh=None,
    )
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Linear Algebra")
    translated = tmp_path / "book-uuid" / "book_trans_md" / "1_trans_zh.md"
    translated.parent.mkdir(parents=True)
    translated.write_text("向量空间在加法与数乘下封闭。", encoding="utf-8")
    monkeypatch.setattr(QuizService, "_chapter_guide_text", staticmethod(lambda *_args: _empty_text()))
    monkeypatch.setattr(QuizService, "_book_guide_text", staticmethod(lambda *_args: _empty_text()))

    context = await QuizService.build_generation_context(book, chapter, "concept_explain")

    assert "Chapter body (direct source" in context
    assert "向量空间在加法与数乘下封闭。" in context
    assert "Learning context" not in context


@pytest.mark.asyncio
async def test_quiz_generation_context_keeps_complete_body_and_guides(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    chapter = SimpleNamespace(
        id=2,
        book_id=1,
        chapter_index="1",
        title_en="Long Chapter",
        title_zh=None,
    )
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Long Book")
    translated = tmp_path / "book-uuid" / "book_trans_md" / "1_trans_zh.md"
    translated.parent.mkdir(parents=True)
    translated.write_text(("正文" * 10000) + "CHAPTER-END", encoding="utf-8")

    async def chapter_guide(*_args):
        return "CHAPTER-GUIDE-END"

    async def book_guide(*_args):
        return "BOOK-GUIDE-END"

    monkeypatch.setattr(QuizService, "_chapter_guide_text", staticmethod(chapter_guide))
    monkeypatch.setattr(QuizService, "_book_guide_text", staticmethod(book_guide))

    context = await QuizService.build_generation_context(book, chapter, "concept_explain")

    assert len(context) > 14000
    assert "CHAPTER-END" in context
    assert "CHAPTER-GUIDE-END" in context
    assert context.endswith("BOOK-GUIDE-END")


async def _empty_text():
    return ""


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
        quiz_mode="book",
        question_type="theorem_understanding",
        personalization_context="Target concept: basis\nReason: missing conditions",
        db=db,
    )

    assert question.source == "book_adaptive"
    assert calls[0]["quiz_mode"] == "book"
    assert calls[0]["personalization_context"] == "Target concept: basis\nReason: missing conditions"


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
    monkeypatch.setattr(QuizService, "weighted_random_question_type", lambda: "proof_strategy")

    async def commit():
        pass

    async def refresh(obj):
        pass

    db = SimpleNamespace(commit=commit, refresh=refresh)

    question = await QuizService.next_chapter_question(
        2,
        quiz_mode="chapter",
        question_type=None,
        personalization_context=None,
        db=db,
    )

    assert question.question_type == "proof_strategy"
    assert question.source == "runtime_batch"
    assert generated_types == QuizService.sparse_bank_question_types("proof_strategy")


def test_learning_profile_storage_paths_use_book_user_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    assert BookStorage.user_profile_path("book-uuid") == tmp_path / "book-uuid" / "book_user" / "User.md"
    assert BookStorage.user_profile_meta_path("book-uuid") == tmp_path / "book-uuid" / "book_user" / "profile_meta.json"

    BookStorage.ensure_book_dirs("book-uuid")
    assert (tmp_path / "book-uuid" / "book_user").is_dir()
