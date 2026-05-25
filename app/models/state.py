from __future__ import annotations

import time
from threading import Lock

from app.models.schemas import ServerStatus


class ServerState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._status: ServerStatus = ServerStatus.stopped
        self._pid: int | None = None
        self._started_at: float | None = None
        self._players: list[str] = []
        self._version: str | None = None

    @property
    def status(self) -> ServerStatus:
        with self._lock:
            return self._status

    @status.setter
    def status(self, value: ServerStatus) -> None:
        with self._lock:
            self._status = value

    @property
    def pid(self) -> int | None:
        with self._lock:
            return self._pid

    @pid.setter
    def pid(self, value: int | None) -> None:
        with self._lock:
            self._pid = value

    @property
    def started_at(self) -> float | None:
        with self._lock:
            return self._started_at

    @started_at.setter
    def started_at(self, value: float | None) -> None:
        with self._lock:
            self._started_at = value

    @property
    def players(self) -> list[str]:
        with self._lock:
            return list(self._players)

    @players.setter
    def players(self, value: list[str]) -> None:
        with self._lock:
            self._players = list(value)

    @property
    def version(self) -> str | None:
        with self._lock:
            return self._version

    @version.setter
    def version(self, value: str | None) -> None:
        with self._lock:
            self._version = value

    @property
    def uptime_seconds(self) -> float | None:
        with self._lock:
            if self._started_at is None:
                return None
            return time.time() - self._started_at

    @property
    def memory_mb(self) -> int | None:
        with self._lock:
            if self._pid is None:
                return None
        try:
            import os
            with open(f"/proc/{self._pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        kb = int(line.split()[1])
                        return kb // 1024
        except (OSError, IOError, ValueError, IndexError):
            pass
        return None

    def mark_started(self, pid: int) -> None:
        with self._lock:
            self._status = ServerStatus.running
            self._pid = pid
            self._started_at = time.time()

    def mark_stopped(self) -> None:
        with self._lock:
            self._status = ServerStatus.stopped
            self._pid = None
            self._started_at = None
            self._players = []

    def mark_crashed(self) -> None:
        with self._lock:
            self._status = ServerStatus.crashed
            self._pid = None

    def reset(self) -> None:
        with self._lock:
            self._status = ServerStatus.stopped
            self._pid = None
            self._started_at = None
            self._players = []
            self._version = None


_state: ServerState | None = None
_state_lock = Lock()


def get_server_state() -> ServerState:
    global _state
    if _state is None:
        with _state_lock:
            if _state is None:
                _state = ServerState()
    return _state
