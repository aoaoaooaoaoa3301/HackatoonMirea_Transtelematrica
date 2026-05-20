import json
from typing import Optional


def _extract_balanced_json(text: str, open_char: str, close_char: str):
    if not text:
        return None

    start = text.find(open_char)
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start:index + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = text.find(open_char, start + 1)
    return None


def extract_json_object(text: str) -> Optional[dict]:
    parsed = _extract_balanced_json(text, "{", "}")
    return parsed if isinstance(parsed, dict) else None


def extract_json_array(text: str) -> Optional[list]:
    parsed = _extract_balanced_json(text, "[", "]")
    return parsed if isinstance(parsed, list) else None
