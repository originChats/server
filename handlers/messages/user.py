import asyncio
from urllib.parse import urlparse
from db import users, roles
from handlers.messages.helpers import _error, _require_user_id, _require_permission
from handlers.websocket_utils import broadcast_to_all, _get_ws_attr
from handlers.helpers.validation import (
    require_user_roles as _require_user_roles,
)
from logger import Logger

ALLOWED_UPDATE_FIELDS = {"username", "nickname"}


async def handle_pfp_set(ws, message, server_data):
    auth_mode = server_data.get("config", {}).get("auth_mode", "rotur")
    if auth_mode not in ("cracked", "cracked-only"):
        return _error("Profile pictures are managed by Rotur for this account", "pfp_set")

    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    if not user_id:
        return _error("User ID is required", "pfp_set")

    url = message.get("url")
    if not url:
        return _error("URL required", "pfp_set")

    parsed = urlparse(url)
    if not parsed.scheme in ("http", "https") or not parsed.netloc:
        return _error("Invalid URL format", "pfp_set")

    if len(url) > 500:
        return _error("URL too long (max 500 characters)", "pfp_set")

    if not users.set_pfp(user_id, url):
        return _error("Failed to update profile picture", "pfp_set")

    username = _get_ws_attr(ws, "username") or user_id
    Logger.add(f"User {username} updated profile picture")
    return {"cmd": "pfp_set", "val": url}


async def handle_pfp_get(ws, message, server_data):
    username = message.get("username")
    if not username:
        return _error("Username required", "pfp_get")

    user_id = users.get_id_by_username(username)
    if not user_id:
        return _error("User not found", "pfp_get")

    pfp_url = users.get_pfp(user_id)
    return {"cmd": "pfp_get", "val": pfp_url, "username": username}


async def handle_user_update(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    error = _require_permission(user_id, "manage_users", match_cmd)
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
    if not target_user:
        return _error("Target user not found", match_cmd)
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
