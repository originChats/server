from typing import Optional
from db import channels, threads, users, unreads
from handlers.websocket_utils import _get_ws_attr, _set_ws_attr, broadcast_to_user
from handlers.helpers.validation import (
    make_error as _error,
    require_user_roles as _require_user_roles,
    require_text_channel_access as _require_text_channel_access,
    get_channel_or_thread_context as _get_channel_or_thread_context,
)
import asyncio


async def handle_unreads_ack(ws, message, server_data):
    match_cmd = "unreads_ack"
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    channel: Optional[str] = message.get("channel")
    thread_id: Optional[str] = message.get("thread_id")
    message_id: Optional[str] = message.get("message_id")

    if not channel and not thread_id:
        return _error("Channel or thread_id is required", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    ctx, err = await _get_channel_or_thread_context(channel, thread_id, user_id, user_roles)
    if err:
        msg, key = err
        return _error(msg, match_cmd)

    if not ctx:
        return _error("Channel or thread not found", match_cmd)

    is_thread = ctx["is_thread"]

    if is_thread and thread_id:
        last_read: Optional[str] = None
        if message_id:
            last_read = message_id
        else:
            all_messages = threads.get_thread_messages(thread_id, 0, 1)
            if all_messages:
                last_read = all_messages[0].get("id")

        if last_read:
            unreads.set_last_read(user_id, last_read, thread_id=thread_id)

        await _broadcast_unreads_update(ws, server_data, user_id, None, thread_id, last_read)
        return {"cmd": "unreads_ack", "thread_id": thread_id, "last_read": last_read}
    else:
        last_read = None
        if message_id:
            last_read = message_id
        else:
            all_messages = channels.get_channel_messages(channel, 0, 1)
            if all_messages:
                last_read = all_messages[0].get("id")

        if last_read:
            unreads.set_last_read(user_id, last_read, channel=channel)

        await _broadcast_unreads_update(ws, server_data, user_id, channel, None, last_read)
        return {"cmd": "unreads_ack", "channel": channel, "last_read": last_read}


async def handle_unreads_get(ws, message, server_data):
    match_cmd = "unreads_get"
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    all_unreads = unreads.get_all_last_reads(user_id)
    result = {}

    all_channels = channels.get_all_channels_for_roles(user_roles)

    for channel_data in all_channels:
        channel_name = channel_data.get("name")
        if channel_data.get("type") != "text":
            continue

        last_read = all_unreads.get(channel_name)
        msg_count = channels.get_channel_message_count(channel_name)

        if last_read:
            messages = channels.get_channel_messages(channel_name, 0, 10000)
            unread_count = len(messages)
            for i, msg in enumerate(messages):
                if msg.get("id") == last_read:
                    unread_count = len(messages) - i - 1
                    break
            result[channel_name] = {
                "last_read": last_read,
                "unread_count": unread_count,
                "total_messages": msg_count
            }
        else:
            result[channel_name] = {
                "last_read": None,
                "unread_count": msg_count,
                "total_messages": msg_count
            }

    return {"cmd": "unreads_get", "unreads": result}


def set_active_channel(ws, channel: Optional[str] = None, thread_id: Optional[str] = None):
    _set_ws_attr(ws, "active_channel", channel)
    _set_ws_attr(ws, "active_thread", thread_id)


def get_active_channel(ws) -> tuple:
    channel = _get_ws_attr(ws, "active_channel")
    thread_id = _get_ws_attr(ws, "active_thread")
    return channel, thread_id


async def auto_ack_on_messages_get(ws, channel: Optional[str], thread_id: Optional[str], user_id: str, server_data):
    set_active_channel(ws, channel, thread_id)

    all_messages = []
    if thread_id:
        all_messages = threads.get_thread_messages(thread_id, 0, 1)
    elif channel:
        all_messages = channels.get_channel_messages(channel, 0, 1)

    if all_messages:
        latest_id = all_messages[0].get("id")
        if latest_id:
            if thread_id:
                unreads.set_last_read(user_id, latest_id, thread_id=thread_id)
            elif channel:
                unreads.set_last_read(user_id, latest_id, channel=channel)

            await _broadcast_unreads_update(ws, server_data, user_id, channel, thread_id, latest_id)


async def _broadcast_unreads_update(ws, server_data, user_id: str, channel: Optional[str], thread_id: Optional[str], last_read: Optional[str]):
    if not server_data or "connected_clients" not in server_data:
        return

    username = users.get_username_by_id(user_id)
    if not username:
        return

    msg = {
        "cmd": "unreads_update",
        "last_read": last_read
    }

    if thread_id:
        msg["thread_id"] = thread_id
    elif channel:
        msg["channel"] = channel

    await broadcast_to_user(server_data["connected_clients"], username, msg, server_data)


async def handle_unreads_count(ws, message, server_data):
    match_cmd = "unreads_count"
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    channel = message.get("channel")
    thread_id = message.get("thread_id")

    if not channel and not thread_id:
        return _error("Channel or thread_id is required", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    if thread_id:
        ctx, err = await _get_channel_or_thread_context(None, thread_id, user_id, user_roles)
        if err:
            msg, key = err
            return _error(msg, match_cmd)
        if not ctx:
            return _error("Thread not found", match_cmd)

        messages = threads.get_thread_messages(thread_id, 0, 10000)
        unread_count, last_read = unreads.get_unread_count_for_thread(user_id, thread_id, messages)
        return {
            "cmd": "unreads_count",
            "thread_id": thread_id,
            "unread_count": unread_count,
            "last_read": last_read,
            "total_messages": len(messages)
        }
    else:
        _, error = _require_text_channel_access(user_id, channel)
        if error:
            return error

        messages = channels.get_channel_messages(channel, 0, 10000)
        unread_count, last_read = unreads.get_unread_count_for_channel(user_id, channel, messages)
        return {
            "cmd": "unreads_count",
            "channel": channel,
            "unread_count": unread_count,
            "last_read": last_read,
            "total_messages": len(messages)
        }
