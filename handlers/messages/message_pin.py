from db import channels, users
from handlers.websocket_utils import _get_ws_attr
from handlers.messages.audit import record
from handlers.helpers.validation import (
    make_error as _error,
    require_user_id as _require_user_id,
    require_user_roles as _require_user_roles,
    require_text_channel_access as _require_text_channel_access,
)


async def handle_message_pin(ws, message, server_data):
    match_cmd = "message_pin"
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    channel_name = message.get("channel")
    if not channel_name:
        return _error("Channel name not provided", match_cmd)

    if not channels.can_user_pin(channel_name, user_roles):
        return _error("You do not have permission to pin messages in this channel", match_cmd)

    message_id = message.get("id")
    if not message_id:
        return _error("Message ID is required", match_cmd)

    pinned = channels.pin_channel_message(channel_name, message_id)
    record("message_pin", ws, target_id=message_id, details={"channel": channel_name})
    username = users.get_username_by_id(user_id)
    if server_data:
        server_data["plugin_manager"].trigger_event("message_pin", ws, {
            "channel": channel_name,
            "id": message_id,
            "pinned": pinned,
            "user_id": user_id,
            "username": username
        }, server_data)
    return {"cmd": "message_pin", "id": message_id, "channel": channel_name, "pinned": pinned, "global": True}


async def handle_message_unpin(ws, message, server_data):
    match_cmd = "message_unpin"
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    channel_name = message.get("channel")
    if not channel_name:
        return _error("Channel name not provided", match_cmd)

    if not channels.can_user_pin(channel_name, user_roles):
        return _error("You do not have permission to pin messages in this channel", match_cmd)

    message_id = message.get("id")
    if not message_id:
        return _error("Message ID is required", match_cmd)

    pinned = channels.unpin_channel_message(channel_name, message_id)
    record("message_unpin", ws, target_id=message_id, details={"channel": channel_name})
    username = users.get_username_by_id(user_id)
    if server_data:
        server_data["plugin_manager"].trigger_event("message_unpin", ws, {
            "channel": channel_name,
            "id": message_id,
            "pinned": pinned,
            "user_id": user_id,
            "username": username
        }, server_data)
    return {"cmd": "message_unpin", "id": message_id, "channel": channel_name, "pinned": pinned, "global": True}


async def handle_messages_pinned(ws, message, server_data):
    match_cmd = "messages_pinned"
    channel_name = message.get("channel")
    if not channel_name:
        return _error("Channel name not provided", match_cmd)

    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    _, error = _require_text_channel_access(user_id, channel_name)
    if error:
        return error

    pinned_messages = channels.get_pinned_messages(channel_name)
    pinned_messages = channels.convert_messages_to_user_format(pinned_messages)
    return {"cmd": "messages_pinned", "channel": channel_name, "messages": pinned_messages}
