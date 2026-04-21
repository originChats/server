from db import channels, threads, users
from handlers.websocket_utils import _get_ws_attr
from handlers.messages.audit import record
from handlers.helpers.validation import (
    make_error as _error,
    require_user_id as _require_user_id,
    require_user_roles as _require_user_roles,
    get_channel_or_thread_context as _get_channel_or_thread_context,
)


async def handle_message_delete(ws, message, server_data):
    match_cmd = "message_delete"
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    message_id = message.get("id")
    channel_name = message.get("channel")
    thread_id = message.get("thread_id")
    if not message_id or (not channel_name and not thread_id):
        return _error("Invalid message delete format", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    ctx, err = await _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
    if err:
        msg, key = err
        return _error(msg, match_cmd)

    if not ctx:
        return _error("Channel or thread not found", match_cmd)

    is_thread = ctx["is_thread"]
    parent_channel = ctx.get("parent_channel") or ctx.get("channel")

    if is_thread and thread_id:
        msg_obj = threads.get_thread_message(thread_id, message_id)
    else:
        msg_obj = channels.get_channel_message(channel_name, message_id)

    if not msg_obj:
        return _error("Message not found or cannot be deleted", match_cmd)

    if msg_obj.get("user") == user_id:
        if not channels.can_user_delete_own(parent_channel, user_roles):
            return _error(f"You do not have permission to delete your own message in this {'thread' if is_thread else 'channel'}", match_cmd)
    else:
        if not channels.does_user_have_permission(parent_channel, user_roles, "delete"):
            return _error("You do not have permission to delete this message", match_cmd)

    if msg_obj.get("attachments"):
        from db import attachments as attachments_db
        for att in msg_obj["attachments"]:
            att_id = att.get("id") if isinstance(att, dict) else att
            if att_id:
                attachments_db.delete_attachment(att_id)

    if is_thread and thread_id:
        if not threads.delete_thread_message(thread_id, message_id):
            return _error("Failed to delete message", match_cmd)

        username = users.get_username_by_id(user_id)
        record("message_delete", ws, target_id=message_id, details={"channel": parent_channel, "thread_id": thread_id})
        if server_data:
            server_data["plugin_manager"].trigger_event("message_delete", ws, {
                "channel": parent_channel,
                "thread_id": thread_id,
                "id": message_id,
                "user_id": user_id,
                "username": username
            }, server_data)
        return {"cmd": "message_delete", "id": message_id, "channel": parent_channel, "thread_id": thread_id, "global": True}
    else:
        if not channels.delete_channel_message(channel_name, message_id):
            return _error("Failed to delete message", match_cmd)

        username = users.get_username_by_id(user_id)
        record("message_delete", ws, target_id=message_id, details={"channel": channel_name})
        if server_data:
            server_data["plugin_manager"].trigger_event("message_delete", ws, {
                "channel": channel_name,
                "id": message_id,
                "user_id": user_id,
                "username": username
            }, server_data)
    return {"cmd": "message_delete", "id": message_id, "channel": channel_name, "global": True}
