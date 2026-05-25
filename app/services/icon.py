from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

from app.config import get_settings
from app.exceptions import IconProcessingError

logger = logging.getLogger(__name__)


class IconService:
    TARGET_SIZE = (64, 64)

    def __init__(self, output_path: Path | None = None) -> None:
        self._output = output_path or get_settings().server_icon_path

    @staticmethod
    def validate_mime(content_type: str) -> None:
        allowed = {"image/png", "image/jpeg", "image/webp"}
        if content_type not in allowed:
            raise IconProcessingError(
                f"Unsupported content type '{content_type}'. "
                f"Allowed: {', '.join(allowed)}"
            )

    async def process(self, data: bytes) -> Path:
        try:
            img = Image.open(io.BytesIO(data))
        except Exception as e:
            raise IconProcessingError(f"Cannot decode image: {e}") from e

        if img.mode not in ("RGBA", "RGB", "P"):
            img = img.convert("RGBA")

        img_resized = img.resize(self.TARGET_SIZE, Image.LANCZOS)

        if img_resized.mode != "RGBA":
            img_resized = img_resized.convert("RGBA")

        buf = io.BytesIO()
        try:
            img_resized.save(buf, format="PNG", optimize=True)
        except Exception as e:
            raise IconProcessingError(f"Cannot encode PNG: {e}") from e

        try:
            self._output.write_bytes(buf.getvalue())
        except OSError as e:
            raise IconProcessingError(f"Cannot write {self._output}: {e}") from e

        logger.info("Server icon saved as 64x64 PNG at %s", self._output)
        return self._output
