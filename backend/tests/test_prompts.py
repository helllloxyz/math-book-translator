from app.services.prompts import PromptId, PromptRegistry


def test_prompt_registry_exposes_versioned_core_prompts():
    translation = PromptRegistry.get(PromptId.TRANSLATE_CHAPTER)
    chat = PromptRegistry.get(PromptId.READER_CHAT)
    quiz = PromptRegistry.get(PromptId.READER_QUIZ)

    assert translation.id == "translate.chapter"
    assert translation.version.startswith("v")
    assert "Output ONLY the translated Markdown" in translation.system
    assert chat.id == "reader.chat"
    assert quiz.id == "reader.quiz"
    assert quiz.system != chat.system
    assert "quiz" in quiz.system.lower()


def test_reader_chat_prompt_requests_markdown_suggested_questions():
    prompt = PromptRegistry.get(PromptId.READER_CHAT)

    assert prompt.version == "v2"
    assert "<!--SUGGESTED_QUESTIONS-->" in prompt.system
    assert "Markdown bullet list of three" in prompt.system
    assert "same language as the user's latest question" in prompt.system


def test_translation_prompt_requests_bold_structural_math_labels_only():
    prompt = PromptRegistry.get(PromptId.TRANSLATE_CHAPTER).system

    assert "bold translated structural math keywords" in prompt.lower()
    assert "headings" in prompt
    assert "theorem/proof labels" in prompt
    assert "numbered environment labels" in prompt
    assert "standalone leading labels" in prompt
    assert "Do not bold ordinary inline occurrences" in prompt
    assert "Theorem, Proof, Definition, Lemma, Proposition, Corollary" in prompt
    assert "Remark, Example, Exercise, Claim, Assumption, Notation" in prompt
    assert "Construction, Algorithm, Axiom" in prompt
    assert "**定理**" in prompt
    assert "**证明**" in prompt


def test_note_title_prompt_requests_short_chinese_title_without_punctuation():
    prompt = PromptRegistry.get(PromptId.NOTE_TITLE).system

    assert "Chinese title" in prompt
    assert "no quotes" in prompt
    assert "no trailing punctuation" in prompt
    assert "max 12 Chinese words" in prompt
    assert "about 24 Chinese characters" in prompt
