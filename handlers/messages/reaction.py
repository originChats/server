from db import channels, users, threads
from handlers.helpers.validation import (
    make_error as _error,
    require_user_id as _require_user_id,
    require_user_roles as _require_user_roles,
)


async def handle_react_add(ws, message, match_cmd, _get_channel_or_thread_context):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    if not user_id:
        return _error("User ID is required", match_cmd)

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
        success = threads.add_thread_reaction(thread_id, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to add reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_add", "id": message_id, "emoji": emoji_str, "channel": parent_channel, "thread_id": thread_id, "from": username, "global": True}
    else:
        success = channels.add_reaction(channel_name, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to add reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_add", "id": message_id, "emoji": emoji_str, "channel": channel_name, "from": username, "global": True}


async def handle_react_remove(ws, message, match_cmd, _get_channel_or_thread_context):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    if not user_id:
        return _error("User ID is required", match_cmd)

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
        success = threads.remove_thread_reaction(thread_id, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to remove reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_remove", "id": message_id, "emoji": emoji_str, "channel": parent_channel, "thread_id": thread_id, "from": username, "global": True}
    else:
        success = channels.remove_reaction(channel_name, message_id, emoji_str, user_id)
        if not success:
            return _error("Failed to remove reaction", match_cmd)
        username = users.get_username_by_id(user_id)
        return {"cmd": "message_react_remove", "id": message_id, "emoji": emoji_str, "channel": channel_name, "from": username, "global": True}
