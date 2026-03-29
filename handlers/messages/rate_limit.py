from db import users
from handlers.messages.helpers import _error, _require_user_id, _require_permission


async def handle_rate_limit_status(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws)
    if error:
        return error

    target_user = message.get("user", user_id)
    target_id = users.get_id_by_username(target_user) or target_user
    user_roles = users.get_user_roles(user_id)

    if target_id != user_id and (not user_roles or "owner" not in user_roles):
        return _error("Access denied: can only check your own rate limit status", match_cmd)

    if not server_data or not server_data.get("rate_limiter"):
        return _error("Rate limiter not available or disabled", match_cmd)

    status = server_data["rate_limiter"].get_user_status(target_id)
    status_username = users.get_username_by_id(target_id)
    return {"cmd": "rate_limit_status", "user": status_username, "status": status}


async def handle_rate_limit_reset(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws)
    if error:
        return error
    error = _require_permission(user_id, "manage_server", match_cmd)
    if error:
        return error

    target_user = message.get("user")
    if not target_user:
        return _error("User parameter is required", match_cmd)

    target_id = users.get_id_by_username(target_user) or target_user
    target_display = users.get_username_by_id(target_id)

    if not server_data or not server_data.get("rate_limiter"):
        return _error("Rate limiter not available or disabled", match_cmd)

    server_data["rate_limiter"].reset_user(target_id)
    return {"cmd": "rate_limit_reset", "user": target_display, "val": f"Rate limit reset for user {target_display}"}
