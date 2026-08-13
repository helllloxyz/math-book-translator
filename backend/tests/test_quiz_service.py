import json
from types import SimpleNamespace

import pytest

from app.models.schema import QuizQuestion
from app.services.book_storage import BookStorage
from app.services.quiz_service import QuizGenerationError, QuizService
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
    assert len(question_types) == QuizService.SPARSE_BANK_TYPE_COUNT
    assert len(set(question_types)) == len(question_types)


def test_candidate_batch_question_types_supports_more_than_three_questions():
    question_types = QuizService.candidate_batch_question_types("proof_strategy", 6)

    assert len(question_types) == 6
    assert question_types[0] == "proof_strategy"
    assert set(question_types) == set(QUIZ_SKILLS)


def test_question_normalization_rejects_missing_question_text_instead_of_falling_back():
    with pytest.raises(ValueError, match="question_text is required"):
        QuizService.normalize_question_data(
            {"target_concepts": ["basis"]},
            book_id=1,
            chapter_id=2,
            question_type="concept_explain",
            quiz_mode="chapter",
            source="runtime",
        )


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
            return (
                '{"question_text":"向量空间为什么需要同时对加法和数乘封闭？",'
                '"target_concepts":["向量空间"],"context_refs":["向量空间"],'
                '"expected_points":["说明两种封闭性各自的作用"]}'
            )

    async def context(*_args, **_kwargs):
        return "SOURCE BODY：向量空间需要同时对加法和数乘封闭。"

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
    assert "Never require a calculation, formula entry" in system_prompt
    assert "ordinary natural language" in system_prompt
    assert "KaTeX-compatible $...$ delimiters" in system_prompt
    assert "escape every LaTeX backslash" in system_prompt
    assert question.question_type == question_type
    assert question.quiz_mode == "chapter"


@pytest.mark.asyncio
async def test_single_question_generation_retries_plain_text_formula_notation(monkeypatch):
    calls = []
    responses = [
        {
            "question_text": "分量函数如何帮助研究映射 F: N → M？",
            "target_concepts": ["分量函数"],
            "context_refs": ["分量函数"],
            "expected_points": ["说明局部坐标的作用"],
        },
        {
            "question_text": r"分量函数如何帮助研究映射 $F \colon N \to M$？",
            "target_concepts": ["分量函数"],
            "context_refs": ["分量函数"],
            "expected_points": ["说明局部坐标的作用"],
        },
    ]

    class FakeTranslator:
        api_key = "configured"

        def __init__(self, **_kwargs):
            pass

        async def complete(self, user_prompt, system_prompt, temperature):
            calls.append((user_prompt, system_prompt, temperature))
            return json.dumps(responses[len(calls) - 1], ensure_ascii=False)

    class FakeDb:
        def add(self, _value):
            pass

        async def commit(self):
            pass

        async def refresh(self, _value):
            pass

    async def context(*_args, **_kwargs):
        return "SOURCE BODY：分量函数将映射的光滑性化为实值函数的光滑性。"

    monkeypatch.setattr("app.services.quiz_service.TranslatorService", FakeTranslator)
    monkeypatch.setattr(QuizService, "build_generation_context", context)
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Book")
    chapter = SimpleNamespace(id=2, chapter_index="1", title_zh="分量", title_en=None)

    question = await QuizService.generate_question(
        book=book,
        chapter=chapter,
        question_type="concept_explain",
        quiz_mode="chapter",
        db=FakeDb(),
    )

    assert len(calls) == 2
    assert "outside KaTeX delimiters" in calls[1][0]
    assert question.question_text == responses[1]["question_text"]


@pytest.mark.asyncio
async def test_candidate_generation_uses_one_call_and_includes_previous_questions(monkeypatch):
    calls = []
    added = []

    class FakeTranslator:
        api_key = "configured"

        def __init__(self, **_kwargs):
            pass

        async def complete(self, user_prompt, system_prompt, temperature):
            calls.append((user_prompt, system_prompt, temperature))
            return json.dumps(
                {
                    "questions": [
                        {
                            "question_type": question_type,
                            "question_text": [
                                "向量空间的封闭性为何同时涉及加法与数乘？",
                                "基定理中的线性无关条件起什么作用？",
                                "紧致性证明中，有限子覆盖如何推进到结论？",
                            ][index],
                            "target_concepts": [
                                ["向量空间"],
                                ["基定理"],
                                ["紧致性"],
                            ][index],
                            "context_refs": [
                                ["向量空间"],
                                ["基定理"],
                                ["有限子覆盖"],
                            ][index],
                            "expected_points": [f"要点 {index + 1}"],
                        }
                        for index, question_type in enumerate(
                            ["concept_explain", "theorem_understanding", "proof_strategy"]
                        )
                    ]
                },
                ensure_ascii=False,
            )

    class FakeDb:
        async def execute(self, _query):
            class Scalars:
                @staticmethod
                def all():
                    return ["题库中的旧题"]

            return SimpleNamespace(scalars=lambda: Scalars())

        def add(self, value):
            added.append(value)

        async def commit(self):
            pass

        async def refresh(self, value):
            value.id = len([item for item in added if item.id is not None]) + 1

    chapter = SimpleNamespace(
        id=2,
        book_id=1,
        chapter_index="1",
        title_en="Vector Spaces",
        title_zh=None,
    )
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Linear Algebra")

    async def context(*_args, **_kwargs):
        return "SOURCE BODY：向量空间、基定理、紧致性与有限子覆盖。"

    async def chapter_or_none(*_args):
        return chapter

    async def book_or_none(*_args):
        return book

    monkeypatch.setattr("app.services.quiz_service.TranslatorService", FakeTranslator)
    monkeypatch.setattr(QuizService, "_chapter_or_none", chapter_or_none)
    monkeypatch.setattr(QuizService, "_book_or_none", book_or_none)
    monkeypatch.setattr(QuizService, "build_generation_context", context)
    monkeypatch.setattr(QuizService, "weighted_random_question_type", lambda: "concept_explain")

    questions = await QuizService._generate_and_store_question_candidates(
        2,
        count=3,
        quiz_mode="chapter",
        question_type=None,
        personalization_context=None,
        previous_questions=["已经问过的老题"],
        db=FakeDb(),
    )

    assert len(calls) == 1
    assert len(questions) == 3
    assert len(added) == 3
    assert "已经问过的老题" in calls[0][0]
    assert "题库中的旧题" in calls[0][0]
    assert "must not repeat or lightly paraphrase" in calls[0][1]
    assert "must explicitly name that source anchor" in calls[0][1]
    assert "KaTeX-compatible $...$ delimiters" in calls[0][1]
    assert {question.question_type for question in questions} == {
        "concept_explain",
        "theorem_understanding",
        "proof_strategy",
    }


@pytest.mark.asyncio
async def test_candidate_json_error_is_exposed_without_writing_fallback(monkeypatch):
    calls = []
    added = []

    class FakeTranslator:
        api_key = "configured"
        provider = "test-provider"
        model_name = "test-model"

        def __init__(self, **_kwargs):
            pass

        async def complete(self, *_args, **_kwargs):
            calls.append(True)
            return '{"questions":[{"question_text":"truncated"}'

    class FakeDb:
        async def execute(self, _query):
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: []),
            )

        def add(self, value):
            added.append(value)

    chapter = SimpleNamespace(
        id=2,
        book_id=1,
        chapter_index="1",
        title_en="Vector Spaces",
        title_zh=None,
    )
    book = SimpleNamespace(id=1, uuid="book-uuid", title="Linear Algebra")

    async def context(*_args, **_kwargs):
        return "SOURCE BODY：向量空间。"

    async def chapter_or_none(*_args):
        return chapter

    async def book_or_none(*_args):
        return book

    monkeypatch.setattr("app.services.quiz_service.TranslatorService", FakeTranslator)
    monkeypatch.setattr(QuizService, "_chapter_or_none", chapter_or_none)
    monkeypatch.setattr(QuizService, "_book_or_none", book_or_none)
    monkeypatch.setattr(QuizService, "build_generation_context", context)

    with pytest.raises(QuizGenerationError, match="may have been truncated; response_chars="):
        await QuizService._generate_and_store_question_candidates(
            2,
            count=6,
            quiz_mode="chapter",
            question_type=None,
            personalization_context=None,
            previous_questions=[],
            db=FakeDb(),
        )

    assert len(calls) == 2
    assert added == []


def test_candidate_quality_gate_rejects_generic_fallback_questions():
    issues = QuizService._candidate_quality_issues(
        {
            "question_text": (
                "请选择「Diffeomorphisms」中的一个重要证明，像口头讲解一样说出证明路线。"
            ),
            "target_concepts": ["Diffeomorphisms"],
            "context_refs": ["Diffeomorphisms"],
            "expected_points": ["说明证明路线"],
        },
        "Chapter body: Diffeomorphisms",
    )

    assert "question delegates source selection to the learner" in issues


def test_candidate_quality_gate_rejects_plain_text_formula_notation():
    issues = QuizService._candidate_quality_issues(
        {
            "question_text": "请解释映射 F: N → M 与分量 y^i ∘ F 的关系。",
            "target_concepts": ["分量函数"],
            "context_refs": ["分量函数"],
            "expected_points": ["说明坐标化的作用"],
        },
        "正文介绍了分量函数。",
    )

    assert "question_text contains mathematical notation outside KaTeX delimiters" in issues

    assert QuizService._contains_plain_text_math("请说明 F(t) = (cos t, sin t) 为什么光滑。")
    assert QuizService._contains_plain_text_math("请说明这个等价链中的 ⇔ 。")


def test_candidate_quality_gate_accepts_katex_delimited_formulas():
    issues = QuizService._candidate_quality_issues(
        {
            "question_text": r"请解释映射 $F \colon N \to M$ 与分量 $y^i \circ F$ 的关系。",
            "target_concepts": ["分量函数"],
            "context_refs": ["分量函数"],
            "expected_points": ["说明坐标化的作用"],
        },
        "正文介绍了分量函数。",
    )

    assert "question_text contains mathematical notation outside KaTeX delimiters" not in issues


def test_bank_reuse_excludes_legacy_fallback_and_keeps_grounded_questions():
    fallback = QuizQuestion(
        source="chapter_candidate_fallback",
        question_type="proof_strategy",
        question_text="请选择本章中的一个重要证明。",
        target_concepts=["Diffeomorphisms"],
        context_refs=[],
        expected_points=["说明证明路线"],
    )
    grounded = QuizQuestion(
        source="chapter_candidate_batch",
        question_type="proof_strategy",
        question_text="逆函数定理如何用于证明局部微分同胚具有光滑的局部逆？",
        target_concepts=["逆函数定理", "局部微分同胚"],
        context_refs=["Inverse Function Theorem"],
        expected_points=["说明非奇异导数如何给出局部可逆性"],
    )

    assert QuizService._is_reusable_bank_question(fallback) is False
    assert QuizService._is_reusable_bank_question(grounded) is True


def test_bank_reuse_excludes_questions_with_plain_text_formula_notation():
    question = QuizQuestion(
        source="chapter_candidate_batch",
        question_type="concept_explain",
        question_text="请解释 F: N → M 为什么光滑。",
        target_concepts=["光滑映射"],
        context_refs=["光滑映射"],
        expected_points=["说明局部表示"],
    )

    assert QuizService._is_reusable_bank_question(question) is False


@pytest.mark.asyncio
async def test_bank_selection_defers_current_conversation_questions_and_marks_display(monkeypatch):
    questions = [
        QuizQuestion(
            id=index,
            book_id=1,
            chapter_id=2,
            quiz_mode="chapter",
            source="chapter_candidate_batch",
            question_type="concept_explain",
            question_text=text,
            target_concepts=[anchor],
            context_refs=[anchor],
            expected_points=["具体语义要点"],
            times_seen=0,
        )
        for index, (text, anchor) in enumerate(
            [
                ("微分同胚为什么必须具有光滑逆映射？", "微分同胚"),
                ("局部微分同胚与逆函数定理如何联系？", "逆函数定理"),
            ],
            start=1,
        )
    ]
    commits = []

    class Result:
        @staticmethod
        def scalars():
            return SimpleNamespace(all=lambda: questions)

    class FakeDb:
        async def execute(self, _query):
            return Result()

        async def commit(self):
            commits.append(True)

        async def refresh(self, _question):
            pass

    selected = await QuizService.choose_candidates_from_bank(
        book_id=1,
        chapter_id=2,
        question_type=None,
        quiz_mode="chapter",
        count=2,
        previous_questions=[questions[0].question_text],
        db=FakeDb(),
    )

    assert [question.id for question in selected] == [2, 1]
    assert [question.times_seen for question in selected] == [1, 1]
    assert commits == [True]


@pytest.mark.asyncio
async def test_chapter_candidate_request_reuses_persisted_bank_without_generation(monkeypatch):
    chapter = SimpleNamespace(id=2, book_id=1)
    book = SimpleNamespace(id=1)
    bank = [
        QuizQuestion(
            id=index,
            book_id=1,
            chapter_id=2,
            quiz_mode="chapter",
            question_type="concept_explain",
            question_text=f"题库题 {index}",
        )
        for index in range(1, 4)
    ]
    bank_reads = []

    async def chapter_or_none(*_args):
        return chapter

    async def book_or_none(*_args):
        return book

    async def choose_candidates(**kwargs):
        bank_reads.append(kwargs["mark_seen"])
        return bank

    async def generate_candidates(*_args, **_kwargs):
        raise AssertionError("a full Chapter Quiz bank must be reused")

    monkeypatch.setattr(QuizService, "_chapter_or_none", chapter_or_none)
    monkeypatch.setattr(QuizService, "_book_or_none", book_or_none)
    monkeypatch.setattr(QuizService, "choose_candidates_from_bank", choose_candidates)
    monkeypatch.setattr(
        QuizService,
        "_generate_and_store_question_candidates",
        generate_candidates,
    )

    questions = await QuizService.generate_question_candidates(
        2,
        count=3,
        quiz_mode="chapter",
        question_type=None,
        personalization_context=None,
        previous_questions=[],
        db=SimpleNamespace(),
    )

    assert questions == bank
    assert bank_reads == [False, True]


@pytest.mark.asyncio
async def test_sparse_chapter_candidate_request_fills_bank_before_selecting(monkeypatch):
    chapter = SimpleNamespace(id=2, book_id=1)
    book = SimpleNamespace(id=1)
    stored = []
    bank_reads = []

    async def chapter_or_none(*_args):
        return chapter

    async def book_or_none(*_args):
        return book

    async def choose_candidates(**kwargs):
        bank_reads.append(kwargs["mark_seen"])
        return list(stored)[:kwargs["count"]]

    async def generate_candidates(*_args, **kwargs):
        assert kwargs["count"] == 6
        stored.extend(
            QuizQuestion(
                id=index,
                book_id=1,
                chapter_id=2,
                quiz_mode="chapter",
                question_type="concept_explain",
                question_text=f"新题 {index}",
            )
            for index in range(1, 7)
        )
        return list(stored)

    monkeypatch.setattr(QuizService, "_chapter_or_none", chapter_or_none)
    monkeypatch.setattr(QuizService, "_book_or_none", book_or_none)
    monkeypatch.setattr(QuizService, "choose_candidates_from_bank", choose_candidates)
    monkeypatch.setattr(
        QuizService,
        "_generate_and_store_question_candidates",
        generate_candidates,
    )

    questions = await QuizService.generate_question_candidates(
        2,
        count=3,
        quiz_mode="chapter",
        question_type=None,
        personalization_context="must not reach Chapter Quiz generation",
        previous_questions=[],
        db=SimpleNamespace(),
    )

    assert questions == stored[:3]
    assert len(stored) == 6
    assert bank_reads == [False, True]


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
async def test_chapter_quiz_generation_context_keeps_complete_body_but_excludes_guides(tmp_path, monkeypatch):
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
    assert "CHAPTER-GUIDE-END" not in context
    assert "BOOK-GUIDE-END" not in context
    assert "Required context: chapter_body" in context


@pytest.mark.asyncio
async def test_book_quiz_generation_context_can_include_guides(tmp_path, monkeypatch):
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
    translated.write_text("章节正文", encoding="utf-8")

    async def chapter_guide(*_args):
        return "CHAPTER-GUIDE"

    async def book_guide(*_args):
        return "BOOK-GUIDE"

    monkeypatch.setattr(QuizService, "_chapter_guide_text", staticmethod(chapter_guide))
    monkeypatch.setattr(QuizService, "_book_guide_text", staticmethod(book_guide))

    context = await QuizService.build_generation_context(
        book,
        chapter,
        "concept_connection",
        quiz_mode="book",
    )

    assert "章节正文" in context
    assert "CHAPTER-GUIDE" in context
    assert context.endswith("BOOK-GUIDE")


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
