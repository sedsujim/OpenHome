from __future__ import annotations

import asyncio
import logging
import shutil
from asyncio.subprocess import Process

from app.config import get_settings

logger = logging.getLogger(__name__)


class TunnelService:
    def __init__(self) -> None:
        self._process: Process | None = None
        self._public_url: str | None = None

    @property
    def active(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def public_url(self) -> str | None:
        return self._public_url

    async def _resolve_agent(self) -> str:
        agent = shutil.which(get_settings().playit_agent_path)
        if agent:
            return agent
        if not get_settings().playit_agent_path.exists():
            raise FileNotFoundError(
                f"playit agent not found at {get_settings().playit_agent_path}"
            )
        return str(get_settings().playit_agent_path)

    async def start(self) -> str | None:
        if self.active:
            logger.warning("Tunnel already active")
            return self._public_url

        settings = get_settings()
        agent = await self._resolve_agent()

        env = {}
        if settings.playit_api_key:
            env["PLAYIT_API_KEY"] = settings.playit_api_key

        logger.info("Starting playit tunnel on port %d", settings.playit_tunnel_port)

        self._process = await asyncio.create_subprocess_exec(
            agent,
            "--port", str(settings.playit_tunnel_port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**env} if env else None,
        )

        async def _read_until_url() -> None:
            if self._process is None or self._process.stdout is None:
                return
            try:
                async for line in self._process.stdout:
                    decoded = line.decode("utf-8", errors="replace").strip()
                    logger.debug("[playit] %s", decoded)
                    if "https://" in decoded or "playit.gg" in decoded:
                        for word in decoded.split():
                            if word.startswith("https://") or word.startswith("http://"):
                                self._public_url = word
                                return
            except Exception:
                pass

        asyncio.create_task(_read_until_url())

        await asyncio.sleep(2)
        return self._public_url

    async def stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None
        self._public_url = None
        logger.info("Tunnel stopped")

    async def get_status(self) -> dict:
        return {
            "active": self.active,
            "url": self._public_url,
            "local_port": get_settings().playit_tunnel_port,
        }


_tunnel_service: TunnelService | None = None
_tunnel_lock = asyncio.Lock()


async def get_tunnel_service() -> TunnelService:
    global _tunnel_service
    if _tunnel_service is None:
        async with _tunnel_lock:
            if _tunnel_service is None:
                _tunnel_service = TunnelService()
    return _tunnel_service
