from app.services.llm_json import extract_json_candidate


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
