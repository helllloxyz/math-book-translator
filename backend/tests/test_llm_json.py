import pytest

from app.services.llm_json import JSONExtractionError, extract_json_candidate


def test_extract_json_candidate_prefers_matching_fenced_json_block():
    response = """
    Draft: {"summary": "ignore me"}

    ```json
    {"summary": "use me", "concepts": [], "key_theorems": [], "dependencies": []}
    ```
    """

    parsed = extract_json_candidate(
        response,
        validator=lambda data: isinstance(data, dict) and "dependencies" in data,
    )

    assert parsed["summary"] == "use me"


def test_extract_json_candidate_falls_back_to_object_scan():
    response = """
    {"model": "example"}

    {"guides": [{"slug": "01-overview", "title": "导读一", "markdown": "# 导读一"}]}
    """

    parsed = extract_json_candidate(
        response,
        validator=lambda data: isinstance(data, dict) and "guides" in data,
    )

    assert parsed["guides"][0]["slug"] == "01-overview"


def test_extract_json_candidate_supports_top_level_array_with_transform():
    parsed = extract_json_candidate(
        '[{"question_text":"题目一"}]',
        validator=lambda data: isinstance(data, (dict, list)),
        transform=lambda data: {"questions": data} if isinstance(data, list) else data,
    )

    assert parsed == {"questions": [{"question_text": "题目一"}]}


def test_extract_json_candidate_supports_array_embedded_in_prose():
    parsed = extract_json_candidate(
        'Here is the result:\n[{"question_text":"题目一"}]\nDone.',
        validator=lambda data: isinstance(data, list),
    )

    assert parsed == [{"question_text": "题目一"}]


def test_extract_json_candidate_repairs_single_latex_backslashes_inside_math():
    parsed = extract_json_candidate(
        r'{"question_text":"请解释 $F \colon N \to \mathbb{R}^m$"}',
        validator=lambda data: isinstance(data, dict),
    )

    assert parsed["question_text"] == r"请解释 $F \colon N \to \mathbb{R}^m$"


def test_extract_json_candidate_preserves_correctly_escaped_latex():
    parsed = extract_json_candidate(
        r'{"question_text":"请解释 $F \\colon N \\to \\mathbb{R}^m$"}',
        validator=lambda data: isinstance(data, dict),
    )

    assert parsed["question_text"] == r"请解释 $F \colon N \to \mathbb{R}^m$"


def test_extract_json_candidate_reports_probable_truncation():
    with pytest.raises(JSONExtractionError, match="may have been truncated; response_chars="):
        extract_json_candidate(
            '{"questions":[{"question_text":"未完成"}',
            validator=lambda data: isinstance(data, dict) and "questions" in data,
        )


def test_extract_json_candidate_reports_schema_mismatch_for_valid_json():
    with pytest.raises(JSONExtractionError, match="did not match the expected schema"):
        extract_json_candidate(
            '{"items":[]}',
            validator=lambda data: isinstance(data, dict) and "questions" in data,
        )
