from __future__ import annotations

import re
from typing import Any

_SECTION_SIGN = "\u00a7"
_COLOR_CODE_RE = re.compile(rf"{_SECTION_SIGN}[0-9a-fklmnor]")
_VALID_COLORS = {
    "0": "black", "1": "dark_blue", "2": "dark_green",
    "3": "dark_aqua", "4": "dark_red", "5": "dark_purple",
    "6": "gold", "7": "gray", "8": "dark_gray", "9": "blue",
    "a": "green", "b": "aqua", "c": "red", "d": "light_purple",
    "e": "yellow", "f": "white",
}
_FORMAT_CODES = {"k": "obfuscated", "l": "bold", "m": "strikethrough", "n": "underline", "o": "italic"}


def strip_motd_codes(raw: str) -> str:
    return _COLOR_CODE_RE.sub("", raw)


def parse_motd_to_json(raw: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    parts = _COLOR_CODE_RE.split(raw)
    codes = _COLOR_CODE_RE.findall(raw)

    current_format: dict[str, Any] = {"text": ""}

    for i, text in enumerate(parts):
        if i > 0 and i - 1 < len(codes):
            code = codes[i - 1][-1]
            if code in _VALID_COLORS:
                current_format["color"] = _VALID_COLORS[code]
            elif code in _FORMAT_CODES:
                current_format[_FORMAT_CODES[code]] = True
            elif code == "r":
                if current_format.get("text"):
                    segment = dict(current_format)
                    segments.append(segment)
                current_format = {"text": ""}

        if text:
            current_format["text"] = current_format.get("text", "") + text

    if current_format.get("text"):
        segments.append(dict(current_format))

    if not segments:
        segments.append({"text": raw})

    return segments


def format_json_motd(segments: list[dict[str, Any]]) -> str:
    import json as _json

    if len(segments) == 1:
        return _json.dumps(segments[0], ensure_ascii=False)
    return _json.dumps(
        {"text": "", "extra": segments}, ensure_ascii=False
    )


def legacy_to_json(raw: str) -> str:
    segments = parse_motd_to_json(raw)
    return format_json_motd(segments)
