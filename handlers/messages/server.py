from db import server_config
from handlers.messages.helpers import _error, _require_user_id, _require_permission
from handlers.messages.audit import record
from handlers.websocket_utils import broadcast_to_all


async def handle_server_update(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    if not server_data:
        return _error("Server data not available", match_cmd)

    updates = {}
    if "name" in message:
        name = message["name"]
        if name is not None and not isinstance(name, str):
            return _error("Name must be a string or null", match_cmd)
        updates["name"] = name

    if "icon" in message:
        icon = message["icon"]
        if icon is not None and not isinstance(icon, str):
            return _error("Icon must be a string or null", match_cmd)
        updates["icon"] = icon

    if "banner" in message:
        banner = message["banner"]
        if banner is not None and not isinstance(banner, str):
            return _error("Banner must be a string or null", match_cmd)
        updates["banner"] = banner

    if not updates:
        return _error("No updates provided", match_cmd)

    updated_info = server_config.update_server_info(
        name=updates.get("name"),
        icon=updates.get("icon"),
        banner=updates.get("banner")
    )

    record("server_update", ws, details=updates)
    server_data["config"] = server_config.get_server_config()

    await broadcast_to_all(server_data["connected_clients"], {
        "cmd": "server_update",
        "name": updated_info["name"],
        "icon": updated_info["icon"],
        "banner": updated_info["banner"]
    }, server_data)

    return {
        "cmd": "server_update",
        "name": updated_info["name"],
        "icon": updated_info["icon"],
        "banner": updated_info["banner"]
    }


async def handle_server_info(ws, message, match_cmd):
    info = server_config.get_server_info()
    return {
        "cmd": "server_info",
        "name": info["name"],
        "icon": info["icon"],
        "banner": info["banner"]
    }
