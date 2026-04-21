from __future__ import annotations

from typing import Any, Optional

from config_store import get_config_value
from db import modlog
from handlers.websocket_utils import _get_ws_attr
from logger import Logger


def _is_enabled() -> bool:
    return get_config_value("modlog", "enabled", default=True)


def record(
    action: str,
    ws: Any,
    *,
    target_id: Optional[str] = None,
    target_name: Optional[str] = None,
    details: Optional[dict] = None,
    category: Optional[str] = None,
) -> None:
    if not _is_enabled():
        return

    try:
        actor_id = _get_ws_attr(ws, "user_id")
        if not actor_id:
            return

        actor_name = _get_ws_attr(ws, "username") or actor_id

        modlog.log_action(
            action=action,
            actor_id=actor_id,
            actor_name=actor_name,
            target_id=target_id,
            target_name=target_name,
            details=details,
            category=category,
        )
    except Exception as exc:
        Logger.error(f"Audit log recording failed for '{action}': {exc}")
