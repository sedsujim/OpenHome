from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings
from app.exceptions import PropertiesParseError

_PROPERTY_LINE = re.compile(r"^\s*([^#\s][^=]*?)\s*=\s*(.*?)\s*$")


class PropertiesEditor:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or get_settings().server_properties_path
        self._raw_lines: list[str] = []
        self._index: dict[int, str] = {}
        self._keys: dict[str, int] = {}

    def read(self) -> dict[str, str]:
        self._raw_lines.clear()
        self._index.clear()
        self._keys.clear()

        if not self._path.exists():
            return {}

        try:
            text = self._path.read_text("utf-8")
        except OSError as e:
            raise PropertiesParseError(f"Cannot read {self._path}: {e}") from e

        result: dict[str, str] = {}
        for i, line in enumerate(text.splitlines()):
            self._raw_lines.append(line)
            m = _PROPERTY_LINE.match(line)
            if m:
                key, val = m.group(1).strip(), m.group(2).strip()
                self._index[i] = key
                self._keys[key] = i
                result[key] = val

        return result

    def apply(self, updates: dict[str, str]) -> dict[str, str]:
        current = self.read()

        for key, value in updates.items():
            if key in self._keys:
                idx = self._keys[key]
                self._raw_lines[idx] = f"{key}={value}"
            else:
                self._raw_lines.append(f"{key}={value}")
                new_idx = len(self._raw_lines) - 1
                self._index[new_idx] = key
                self._keys[key] = new_idx
            current[key] = value

        self._flush()
        return current

    def _flush(self) -> None:
        try:
            self._path.write_text("\n".join(self._raw_lines) + "\n", "utf-8")
        except OSError as e:
            raise PropertiesParseError(f"Cannot write {self._path}: {e}") from e

    def get(self, key: str, default: str | None = None) -> str | None:
        current = self.read()
        return current.get(key, default)
