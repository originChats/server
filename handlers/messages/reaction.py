import asyncio
from db import channels, users, threads
from handlers.websocket_utils import _get_ws_attr


def _error(error_message, match_cmd):
    if match_cmd:
        return {"cmd": "error", "src": match_cmd, "val": error_message}
    return {"cmd": "error", "val": error_message}


def _require_user_id(ws, error_message: str = "User not authenticated"):
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return None, _error(error_message, None)
    return user_id, None


def _require_user_roles(user_id, *, requiredRoles=[], forbiddenRoles=[], missing_roles_message="User roles not found"):
    user_roles = users.get_user_roles(user_id)
    for role in requiredRoles:
        if not user_roles or role not in user_roles:
            return None, _error(f"Access denied: '{role}' role required", None)
    if not user_roles:
        return None, _error(missing_roles_message, None)
    return user_roles, None


async def handle_react_add(ws, message, match_cmd, _get_channel_or_thread_context):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    user_roles, error = _require_user_roles(user_id)
    if error:
        return error

    channel_name = message.get("channel")
    thread_id = message.get("thread_id")
    message_id = message.get("id")
    emoji_str = message.get("emoji")

    if not message_id or not emoji_str:
        return _error("Message ID and emoji are required", match_cmd)

    ctx, err = _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
    if err:
        msg, key = err
        return _error(msg, match_cmd)

    if not ctx:
        return _error("Message not found", match_cmd)

    is_thread = ctx["is_thread"]
    parent_channel = ctx.get("parent_channel") or ctx.get("channel")

    if not channels.can_user_react(parent_channel, user_roles):
        return _error("You do not have permission to add reactions to this message", match_cmd)

    if is_thread and thread_id:
        msg_obj = threads.get_thread_message(thread_id, message_id)
        if not msg_obj:
            return _error("Message not found", match_cmd)
        success = await asyncio.to_thread(threads.add_thread_reaction, thread_id, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to add reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_add", "id": message_id, "emoji": emoji_str, "channel": parent_channel, "thread_id": thread_id, "from": username, "global": True}
    else:
        success = await asyncio.to_thread(channels.add_reaction, channel_name, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to add reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_add", "id": message_id, "emoji": emoji_str, "channel": channel_name, "from": username, "global": True}


async def handle_react_remove(ws, message, match_cmd, _get_channel_or_thread_context):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    channel_name = message.get("channel")
    thread_id = message.get("thread_id")
    message_id = message.get("id")
    emoji_str = message.get("emoji")

    if not message_id or not emoji_str:
        return _error("Message ID and emoji are required", match_cmd)

    user_roles, error = _require_user_roles(user_id)
    if error:
        return error

    ctx, err = _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
    if err:
        msg, key = err
        return _error(msg, match_cmd)

    if not ctx:
        return _error("Message not found", match_cmd)

    is_thread = ctx["is_thread"]
    parent_channel = ctx.get("parent_channel") or ctx.get("channel")

    if not channels.can_user_react(parent_channel, user_roles):
        return _error("You do not have permission to remove reactions from this message", match_cmd)

    if is_thread and thread_id:
        msg_obj = threads.get_thread_message(thread_id, message_id)
        if not msg_obj:
            return _error("Message not found", match_cmd)
        success = await asyncio.to_thread(threads.remove_thread_reaction, thread_id, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to remove reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_remove", "id": message_id, "emoji": emoji_str, "channel": parent_channel, "thread_id": thread_id, "from": username, "global": True}
    else:
        success = await asyncio.to_thread(channels.remove_reaction, channel_name, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to remove reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_remove", "id": message_id, "emoji": emoji_str, "channel": channel_name, "from": username, "global": True}
