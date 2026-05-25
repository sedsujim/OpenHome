from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ServerStatus(str, Enum):
    created = "created"
    provisioning = "provisioning"
    stopped = "stopped"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    crashed = "crashed"
    error = "error"


class InstanceState(BaseModel):
    status: ServerStatus = ServerStatus.stopped
    pid: int | None = None
    uptime_seconds: float | None = None
    memory_mb: int | None = None
    players: list[str] = Field(default_factory=list)
    version: str | None = None


class StartRequest(BaseModel):
    force: bool = False


class CommandRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=512)

    @field_validator("command")
    @classmethod
    def no_newlines(cls, v: str) -> str:
        if "\n" in v:
            raise ValueError("command must not contain newlines")
        return v.strip()


class PropertiesPayload(BaseModel):
    properties: dict[str, str]


class MotdSegment(BaseModel):
    text: str = ""
    bold: bool = False
    italic: bool = False
    underlined: bool = False
    strikethrough: bool = False
    obfuscated: bool = False
    color: str | None = None


class MotdPayload(BaseModel):
    raw: str | None = None
    json_motd: list[MotdSegment] | None = None


class TunnelStatus(BaseModel):
    active: bool = False
    url: str | None = None
    local_port: int = 25565


class DnsStatus(BaseModel):
    domain: str | None = None
    ip: str | None = None
    last_update: str | None = None
    token_configured: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    server: InstanceState
    tunnel: TunnelStatus
    dns: DnsStatus
    version: str


class WsMessage(BaseModel):
    type: str
    data: Any = None


class ServerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    minecraft_version: str = "latest"
    loader: str = "paper"
    ram_mb: int = 1024
    max_players: int = 10


class ProvisionRequest(BaseModel):
    minecraft_version: str = "latest"
    loader: str = "paper"


class ServerResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    minecraft_version: str
    loader: str
    plan: str
    ram_mb: int
    max_players: int
    created_at: str | None = None


class PlanLimitsResponse(BaseModel):
    id: str
    name: str
    max_servers: int
    ram_mb: int
    storage_gb: int
    max_players: int
    auto_stop_minutes: int
    allow_plugins: bool
    allow_world_upload: bool
    allow_backups: bool
    allow_custom_domain: bool
    priority_startup: bool = False
    admin_controlled: bool = False
    available: bool = True


class ProfileResponse(BaseModel):
    id: str
    email: str = ""
    username: str | None = None
    plan: str
    limits: PlanLimitsResponse


class ServerStatusResponse(BaseModel):
    status: str
    container_name: str | None = None
    container_id: str | None = None
    uptime_seconds: float | None = None
    memory_mb: int | None = None
    players: list[str] = Field(default_factory=list)
    version: str | None = None
