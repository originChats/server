from db import users, roles
from handlers.messages.helpers import _error, _require_user_id
from handlers.helpers.validation import get_ws_username as _get_ws_username
from handlers.websocket_utils import broadcast_to_all, _get_ws_attr, _set_ws_attr


async def handle_status_set(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    status = message.get("status")
    if not status:
        return _error("Status is required", match_cmd)

    text = message.get("text")

    if not users.set_status(user_id, status, text):
        return _error("Invalid status. Must be one of: online, idle, dnd, offline, invisible", match_cmd)

    username = _get_ws_username(ws)
    status_data = {"status": status, "text": text or ""}

    previous_status = _get_ws_attr(ws, "status", {}).get("status", "online")
    is_becoming_invisible = status == "invisible" and previous_status != "invisible"
    is_leaving_invisible = previous_status == "invisible" and status != "invisible"
    broadcast_status_get = None

    if is_becoming_invisible:
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "user_disconnect",
            "username": username
        }, server_data)
    elif is_leaving_invisible:
        user_data = users.get_user(user_id)
        user_roles = user_data.get("roles", []) if user_data else []
        color = roles.get_user_color(user_roles)
        await broadcast_to_all(server_data["connected_clients"], {
            "cmd": "user_connect",
            "user": {
                "username": username,
                "roles": user_roles,
                "color": color
            }
        }, server_data)
        broadcast_status_get = {
            "cmd": "status_get",
            "username": username,
            "status": status_data,
            "global": True
        }
    elif status != "invisible":
        broadcast_status_get = {
            "cmd": "status_get",
            "username": username,
            "status": status_data,
            "global": True
        }

    _set_ws_attr(ws, "status", status_data)

    if broadcast_status_get:
        return broadcast_status_get
    return {"cmd": "status_set", "status": status_data, "global": True}


async def handle_status_get(ws, message, match_cmd, server_data):
    _, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    target = message.get("user")
    if not target:
        return _error("User parameter is required", match_cmd)

    target_id = users.get_id_by_username(target) or target
    if not users.user_exists(target_id):
        return _error("User not found", match_cmd)

    target_status = users.get_status(target_id)
    target_username = users.get_username_by_id(target_id)

    return {"cmd": "status", "username": target_username, "status": target_status}

