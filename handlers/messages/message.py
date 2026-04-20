"""Message and typing handlers extracted from the monolithic handle() function."""

from db import channels, users, threads
from handlers.helpers.validation import (
    make_error as _error,
    config_value as _config_value,
    require_user_id as _require_user_id,
    require_user_roles as _require_user_roles,
    get_channel_or_thread_context as _get_channel_or_thread_context,
)
from handlers.helpers.mentions import (
    get_message_pings,
    validate_role_mentions_permissions,
)
from handlers.websocket_utils import broadcast_to_all, _get_ws_attr, _set_ws_attr
from handlers import push as push_handler
from logger import Logger
import time
import uuid


async def handle_message_new(ws, message, server_data):
    match_cmd = "message_new"
    if server_data is None:
        return _error("Server data not available", match_cmd)

    channel_name = message.get("channel")
    thread_id = message.get("thread_id")
    content = message.get("content", "")
    reply_to = message.get("reply_to")
    embeds = message.get("embeds")
    attachments = message.get("attachments")
    user_id = _get_ws_attr(ws, "user_id")

    if (not channel_name and not thread_id) or (not content and not attachments) or not user_id:
        missing_fields = []
        if not channel_name and not thread_id:
            missing_fields.append("channel or thread_id")
        if not content and not attachments:
            missing_fields.append("content or attachments")
        if not user_id:
            missing_fields.append("user_id")
        return _error(f"Missing fields: {', '.join(missing_fields)}", match_cmd)

    content = content.strip()
    if not content and not attachments:
        return _error("Message content or attachments cannot be empty", match_cmd)

    if embeds:
        from handlers.helpers.validation import validate_embeds
        is_valid, error_msg = validate_embeds(embeds)
        if not is_valid:
            return _error(error_msg, match_cmd)

    max_length = _config_value(server_data, "limits", "post_content", default=2000)
    if len(content) > max_length:
        return _error(f"Message too long. Maximum length is {max_length} characters", match_cmd)

    if server_data and server_data.get("rate_limiter"):
        is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
        if not is_allowed:
            return {"cmd": "rate_limit", "reason": reason, "length": int(wait_time * 1000)}

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    is_valid, error_msg = validate_role_mentions_permissions(content, user_roles)
    if not is_valid:
        return _error(error_msg, match_cmd)

    parent_channel = None
    if thread_id:
        thread_data = threads.get_thread(thread_id)
        if not thread_data:
            return _error("Thread not found", match_cmd)
        if threads.is_thread_locked(thread_id):
            return _error("This thread is locked", match_cmd)
        if threads.is_thread_archived(thread_id):
            threads.update_thread(thread_id, {"archived": False})
        parent_channel = thread_data.get("parent_channel")
        if not channels.does_user_have_permission(parent_channel, user_roles, "send"):
            return _error("You do not have permission to send messages in this thread", match_cmd)
    else:
        if not channels.channel_exists(channel_name):
            return _error("Channel not found", match_cmd)
        if not channels.does_user_have_permission(channel_name, user_roles, "send"):
            return _error("You do not have permission to send messages in this channel", match_cmd)
        channel_info = channels.get_channel(channel_name)
        if channel_info and channel_info.get("type") != "text":
            return _error("Cannot send messages in this channel type", match_cmd)

    replied_message = None
    if reply_to:
        if thread_id:
            replied_message = threads.get_thread_message(thread_id, reply_to)
        else:
            replied_message = channels.get_channel_message(channel_name, reply_to)
        if not replied_message:
            return _error("The message you're trying to reply to was not found", match_cmd)

    validated_attachments = []
    if attachments:
        from db import attachments as attachments_db
        attachment_config = server_data.get("config", {}).get("attachments", {})
        if not attachment_config.get("enabled", True):
            return _error("Attachments are disabled", match_cmd)
        if not isinstance(attachments, list):
            return _error("Attachments must be an array", match_cmd)
        for att in attachments:
            if not isinstance(att, dict):
                return _error("Each attachment must be an object", match_cmd)
            att_id = att.get("id")
            if not att_id:
                return _error("Attachment ID is required", match_cmd)
            attachment = attachments_db.get_attachment(att_id)
            if not attachment:
                return _error(f"Attachment {att_id} not found or expired", match_cmd)
            if attachment.get("uploader_id") != user_id:
                return _error("You can only attach your own uploads", match_cmd)
            base_url = ""
            if "server" in server_data.get("config", {}) and "url" in server_data["config"]["server"]:
                base_url = server_data["config"]["server"]["url"].rstrip("/")
            validated_attachments.append(attachments_db.get_attachment_info_for_client(attachment, base_url))

    out_msg = {
        "user": user_id,
        "content": content,
        "timestamp": time.time(),
        "id": str(uuid.uuid4())
    }
    if embeds:
        out_msg["embeds"] = embeds
    if validated_attachments:
        out_msg["attachments"] = validated_attachments
    if reply_to and replied_message:
        out_msg["reply_to"] = {"id": reply_to, "user": replied_message.get("user")}
    if message.get("ping") is not None:
        out_msg["ping"] = bool(message.get("ping"))

    if validated_attachments:
        from db import attachments as attachments_db
        att_ids = [a["id"] for a in validated_attachments]
        attachments_db.mark_attachments_referenced(att_ids)

    effective_channel = channel_name if not thread_id else (channel_name or parent_channel)

    if thread_id:
        threads.save_thread_message(thread_id, out_msg)
        out_msg_for_client = threads.convert_messages_to_user_format([out_msg])[0]
    else:
        channels.save_channel_message(channel_name, out_msg)
        out_msg_for_client = channels.convert_messages_to_user_format([out_msg])[0]

    if not out_msg_for_client:
        return _error("Failed to save message", match_cmd)

    if "ping" in out_msg:
        out_msg_for_client["ping"] = out_msg["ping"]

    if out_msg_for_client.get("reply_to") and out_msg_for_client["reply_to"].get("user"):
        reply_user = out_msg_for_client["reply_to"]["user"]
        if reply_user and isinstance(reply_user, str):
            resolved_username = users.get_username_by_id(reply_user)
            if resolved_username:
                out_msg_for_client["reply_to"]["user"] = resolved_username

    username = users.get_username_by_id(user_id)
    pings = get_message_pings(content, user_roles)

    reply_author_id = None
    if reply_to and replied_message:
        reply_ping_enabled = message.get("ping", True)
        if reply_ping_enabled:
            original_author_id = replied_message.get("user")
            if original_author_id and out_msg_for_client["reply_to"]["user"]:
                reply_author_id = original_author_id
                if "replies" not in pings:
                    pings["replies"] = []
                pings["replies"].append(out_msg_for_client["reply_to"]["user"])

    if pings.get("users") or pings.get("roles") or "replies" in pings:
        out_msg_for_client["pings"] = pings

    if server_data and "plugin_manager" in server_data:
        try:
            server_data["plugin_manager"].trigger_event("new_message", ws, {
                "content": content, "channel": channel_name,
                "user_id": user_id, "username": username, "message": out_msg
            }, server_data)
        except Exception:
            pass

    for mentioned_username in (pings.get("users") or set()):
        if mentioned_username != username and server_data and not push_handler.is_user_online(mentioned_username, server_data):
            push_handler.send_push_notification(
                username=mentioned_username, title=f"#{effective_channel} — {username}",
                body=content, extra_data={"channelName": effective_channel})

    for mentioned_role in (pings.get("roles") or []):
        for member_username in users.get_usernames_by_role(mentioned_role):
            if member_username != username and server_data and not push_handler.is_user_online(member_username, server_data):
                push_handler.send_push_notification(
                    username=member_username, title=f"#{effective_channel} — {username} mentioned @{mentioned_role}",
                    body=content, extra_data={"channelName": effective_channel})

    if reply_to and replied_message and reply_author_id:
        original_author = users.get_username_by_id(reply_author_id)
        if message.get("ping", True) and original_author and original_author != username:
            if not push_handler.is_user_online(original_author, server_data):
                push_handler.send_push_notification(
                    username=original_author, title=f"#{effective_channel} — {username} replied",
                    body=content, extra_data={"channelName": effective_channel})

    return {"cmd": "message_new", "message": out_msg_for_client, "channel": effective_channel,
            "thread_id": thread_id if thread_id else None, "global": True}


async def handle_typing(ws, message, server_data):
    match_cmd = "typing"
    user_id, error = _require_user_id(ws)
    if error:
        return error

    if server_data and server_data.get("rate_limiter"):
        is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
        if not is_allowed:
            return {"cmd": "rate_limit", "reason": reason, "length": int(wait_time * 1000)}

    channel_name = message.get("channel")
    if not channel_name:
        return _error("Channel name not provided", match_cmd)

    if not channels.channel_exists(channel_name):
        return _error("Channel not found", match_cmd)

    user_data = users.get_user(user_id)
    if not user_data:
        return _error("User not found", match_cmd)

    allowed_channels = channels.get_all_channels_for_roles(user_data.get("roles", []))
    allowed_text_channel_names = [c.get("name") for c in allowed_channels if c.get("type") == "text"]
    if channel_name not in allowed_text_channel_names:
        return _error("Access denied to this channel", match_cmd)

    username = users.get_username_by_id(user_id)
    return {"cmd": "typing", "channel": channel_name, "user": username, "global": True}
