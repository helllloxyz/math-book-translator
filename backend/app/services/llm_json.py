import json
import re
from collections.abc import Callable
from typing import Any


class JSONExtractionError(ValueError):
    """Raised when an LLM response has no JSON value matching the expected schema."""


def parse_json_text(text: str) -> Any | None:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def iter_fenced_json_payloads(text: str):
    pattern = r"```[ \t]*json[ \t\r\n]+(.*?)```"
    for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
        yield match.group(1)


def iter_json_objects(text: str):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            parsed, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        yield parsed


def iter_json_arrays(text: str):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\[", text):
        try:
            parsed, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        yield parsed


def _unclosed_json_delimiters(text: str) -> bool:
    stack = []
    in_string = False
    escaped = False
    pairs = {"}": "{", "]": "["}
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if not stack or stack[-1] != pairs[char]:
                return True
            stack.pop()
    return in_string or bool(stack)


def _extraction_error(text: str, parsed_whole: Any | None) -> JSONExtractionError:
    response_chars = len(text)
    if not text.strip():
        reason = "the model returned an empty response"
    elif parsed_whole is not None:
        reason = f"valid JSON did not match the expected schema (top-level {type(parsed_whole).__name__})"
    elif _unclosed_json_delimiters(text):
        reason = "the response contains unclosed JSON delimiters and may have been truncated"
    else:
        reason = "the response is not valid JSON or does not match the expected schema"
    return JSONExtractionError(f"{reason}; response_chars={response_chars}")


def extract_json_candidate(
    text: str,
    validator: Callable[[Any], bool],
    *,
    transform: Callable[[Any], Any] | None = None,
) -> Any:
    parsed_whole = parse_json_text(text)
    if parsed_whole is not None and validator(parsed_whole):
        return transform(parsed_whole) if transform is not None else parsed_whole

    for payload in iter_fenced_json_payloads(text):
        parsed = parse_json_text(payload)
        if parsed is not None and validator(parsed):
            return transform(parsed) if transform is not None else parsed

    for parsed in iter_json_objects(text):
        if validator(parsed):
            return transform(parsed) if transform is not None else parsed

    for parsed in iter_json_arrays(text):
        if validator(parsed):
            return transform(parsed) if transform is not None else parsed

    raise _extraction_error(text, parsed_whole)
