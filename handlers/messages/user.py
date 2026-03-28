from db import users
from handlers.messages.helpers import _error, _require_user_id, _require_user_roles
from handlers.websocket_utils import broadcast_to_all

ALLOWED_UPDATE_FIELDS = {"username", "nickname"}


async def handle_user_update(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    if not server_data:
        return _error("Server data not available", match_cmd)

    target = message.get("user")
    if not target:
        return _error("User parameter is required", match_cmd)

    target_id = users.get_id_by_username(target) or target
    if not users.user_exists(target_id):
        return _error("User not found", match_cmd)

    updates = message.get("updates")
    if not updates or not isinstance(updates, dict):
        return _error("Updates must be an object", match_cmd)

    for field in updates:
        if field not in ALLOWED_UPDATE_FIELDS:
            return _error(f"Cannot update field: {field}", match_cmd)

    if "username" in updates:
        if not isinstance(updates["username"], str) or not updates["username"].strip():
            return _error("Username must be a non-empty string", match_cmd)

    if "nickname" in updates:
        nick = updates["nickname"]
        if nick is not None and not isinstance(nick, str):
            return _error("Nickname must be a string or null", match_cmd)

    target_user = users.get_user(target_id)
    new_username = target_user.get("username")
    new_nickname = target_user.get("nickname")

    if "username" in updates:
        users.update_user_username(target_id, updates["username"])
        new_username = updates["username"]

    if "nickname" in updates:
        if updates["nickname"] is None:
            users.clear_nickname(target_id)
            new_nickname = None
        else:
            users.set_nickname(target_id, updates["nickname"])
            new_nickname = updates["nickname"]

    await broadcast_to_all(server_data["connected_clients"], {
        "cmd": "user_updated",
        "user_id": target_id,
        "username": new_username,
        "nickname": new_nickname
    }, server_data)

    return {
        "cmd": "user_update",
        "user": new_username,
        "nickname": new_nickname
    }
