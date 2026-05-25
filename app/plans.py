from __future__ import annotations

from app.exceptions import ServerLimitError


FREE_PLAN = {
    "id": "free",
    "name": "OpenHome Free",
    "max_servers": 1,
    "ram_mb": 1024,
    "storage_gb": 2,
    "max_players": 10,
    "auto_stop_minutes": 10,
    "allow_plugins": True,
    "allow_world_upload": True,
    "allow_backups": False,
    "allow_custom_domain": False,
    "priority_startup": False,
    "admin_controlled": False,
    "available": True,
}

PLUS_PLAN = {
    "id": "plus",
    "name": "OpenHome Plus",
    "max_servers": 3,
    "ram_mb": 4096,
    "storage_gb": 10,
    "max_players": 25,
    "auto_stop_minutes": 120,
    "allow_plugins": True,
    "allow_world_upload": True,
    "allow_backups": True,
    "allow_custom_domain": True,
    "priority_startup": True,
    "admin_controlled": True,
    "available": False,
}


def get_plan_limits(plan_id: str) -> dict:
    if plan_id == "plus":
        return PLUS_PLAN
    return FREE_PLAN


def normalize_plan_id(plan_id: str | None) -> str:
    if plan_id == "plus":
        return "plus"
    return "free"


async def assert_can_create_server(user_id: str, current_server_count: int, plan_id: str = "free") -> None:
    del user_id
    plan = get_plan_limits(normalize_plan_id(plan_id))
    if current_server_count >= plan["max_servers"]:
        raise ServerLimitError(
            f"{plan['name']} allows up to {plan['max_servers']} server(s). "
            "Delete an existing server before creating another."
        )


async def assert_server_owner(user_id: str, server_owner_id: str) -> None:
    if user_id != server_owner_id:
        raise PermissionError("You do not own this server")
