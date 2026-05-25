from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.exceptions import DnsUpdateError

logger = logging.getLogger(__name__)


class DnsService:
    DUCKDNS_URL = "https://www.duckdns.org/update"

    def __init__(self) -> None:
        self._last_update: datetime | None = None
        self._last_ip: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def configured(self) -> bool:
        s = get_settings()
        return bool(s.duckdns_token and s.duckdns_domain)

    async def update(self, ip: str | None = None) -> str:
        settings = get_settings()
        if not self.configured:
            raise DnsUpdateError("DuckDNS not configured")

        params = {"token": settings.duckdns_token, "domain": settings.duckdns_domain}
        if ip:
            params["ip"] = ip

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(self.DUCKDNS_URL, params=params)
                text = resp.text.strip()
        except httpx.HTTPError as e:
            raise DnsUpdateError(f"DuckDNS API error: {e}") from e

        if text.upper() != "OK":
            raise DnsUpdateError(f"DuckDNS returned: {text}")

        self._last_update = datetime.now(timezone.utc)
        self._last_ip = ip
        logger.info("DuckDNS updated: %s -> %s", settings.duckdns_domain, ip or "auto")
        return text

    async def start_auto_update(self, interval: int = 300) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._auto_updater(interval))

    async def _auto_updater(self, interval: int) -> None:
        while self._running:
            try:
                await self.update()
            except Exception as e:
                logger.warning("DuckDNS auto-update failed: %s", e)
            await asyncio.sleep(interval)

    async def stop_auto_update(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def get_status(self) -> dict:
        return {
            "domain": get_settings().duckdns_domain,
            "ip": self._last_ip,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "token_configured": self.configured,
        }


_dns_service: DnsService | None = None
_dns_lock = asyncio.Lock()


async def get_dns_service() -> DnsService:
    global _dns_service
    if _dns_service is None:
        async with _dns_lock:
            if _dns_service is None:
                _dns_service = DnsService()
    return _dns_service
