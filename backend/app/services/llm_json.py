import json
import re
from collections.abc import Callable
from typing import Any


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


def extract_json_candidate(
    text: str,
    validator: Callable[[Any], bool],
    *,
    transform: Callable[[Any], Any] | None = None,
) -> Any:
    for payload in iter_fenced_json_payloads(text):
        parsed = parse_json_text(payload)
        if parsed is not None and validator(parsed):
            return transform(parsed) if transform is not None else parsed

    for parsed in iter_json_objects(text):
        if validator(parsed):
            return transform(parsed) if transform is not None else parsed

    raise ValueError("No valid JSON object found.")
