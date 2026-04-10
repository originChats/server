from db import channels, threads, users
from handlers.websocket_utils import _get_ws_attr
from handlers.messages.unreads import auto_ack_on_messages_get
from handlers.helpers.validation import (
    make_error as _error,
    require_user_id as _require_user_id,
    require_user_roles as _require_user_roles,
    require_text_channel_access as _require_text_channel_access,
    get_channel_or_thread_context as _get_channel_or_thread_context,
    config_value as _config_value,
)


async def handle_messages_get(ws, message, server_data):
    match_cmd = "messages_get"
    channel_name = message.get("channel")
    thread_id = message.get("thread_id")
    start = message.get("start", 0)
    limit = message.get("limit", 100)
    end = start + limit

    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

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
        messages = threads.get_thread_messages(thread_id, start, limit)
        messages = threads.convert_messages_to_user_format(messages)
        await auto_ack_on_messages_get(ws, parent_channel, thread_id, user_id, server_data)
        return {"cmd": "messages_get", "channel": parent_channel, "thread_id": thread_id, "messages": messages, "range": {"start": start, "end": end}}
    else:
        _, error = _require_text_channel_access(user_id, channel_name)
        if error:
            return error
        messages = channels.get_channel_messages(channel_name, start, limit)
        messages = channels.convert_messages_to_user_format(messages)
        await auto_ack_on_messages_get(ws, channel_name, None, user_id, server_data)
        return {"cmd": "messages_get", "channel": channel_name, "messages": messages, "range": {"start": start, "end": end}}


async def handle_messages_around(ws, message, server_data):
    match_cmd = "messages_around"
    channel_name = message.get("channel")
    thread_id = message.get("thread_id")
    around = message.get("around")

    if not around:
        return _error("around (message ID) is required", match_cmd)

    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

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

    bounds = message.get("bounds", {"above": 50, "below": 50})
    above = min(bounds.get("above", 50), 200)
    below = min(bounds.get("below", 50), 200)

    messages = None
    start_idx = None
    end_idx = None

    if is_thread and thread_id:
        messages, start_idx, end_idx = threads.get_thread_messages_around(thread_id, around, above, below)
    elif channel_name:
        _, error = _require_text_channel_access(user_id, channel_name)
        if error:
            return error
        messages, start_idx, end_idx = channels.get_channel_messages_around(channel_name, around, above, below)

    if messages is None:
        return _error("Message not found", match_cmd)

    messages = channels.convert_messages_to_user_format(messages)
    return {"cmd": "messages_around", "channel": parent_channel if is_thread else channel_name, "thread_id": thread_id if is_thread else None, "messages": messages, "range": {"start": start_idx, "end": end_idx}}


async def handle_messages_search(ws, message, server_data):
    match_cmd = "messages_search"
    channel_name = message.get("channel")
    query = message.get("query")
    if not channel_name or not query:
        return _error("Channel name and query are required", match_cmd)
    
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)
    
    _, error = _require_text_channel_access(user_id, channel_name)
    if error:
        return error

    search_results = channels.search_channel_messages(channel_name, query)
    search_limit = _config_value(server_data, "limits", "search_results", default=30)
    try:
        search_limit = int(search_limit)
    except (TypeError, ValueError):
        search_limit = 30
    if search_limit < 1:
        search_limit = 1
    search_results = search_results[:search_limit]
    search_results = channels.convert_messages_to_user_format(search_results)
    return {"cmd": "messages_search", "channel": channel_name, "query": query, "results": search_results}


async def handle_message_get(ws, message, server_data):
    match_cmd = "message_get"
    channel_name = message.get("channel")
    thread_id = message.get("thread_id")
    message_id = message.get("id")

    if not message_id or (not channel_name and not thread_id):
        return _error("Channel/thread and message ID are required", match_cmd)

    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)

    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)

    ctx, err = await _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
    if err:
        msg, key = err
        return _error(msg, match_cmd)

    if not ctx:
        return _error("Channel not found", match_cmd)
    
    is_thread = ctx["is_thread"]
    parent_channel = ctx.get("parent_channel") or ctx.get("channel")
    
    if is_thread and thread_id:
        msg = threads.get_thread_message(thread_id, message_id)
        if not msg:
            return _error("Message not found", match_cmd)
        msg = threads.convert_messages_to_user_format([msg])[0]
        return {"cmd": "message_get", "channel": parent_channel, "thread_id": thread_id, "message": msg}
    elif channel_name:
        _, error = _require_text_channel_access(user_id, channel_name)
        if error:
            return error
        msg = channels.get_channel_message(channel_name, message_id)
        if not msg:
            return _error("Message not found", match_cmd)
        msg = channels.convert_messages_to_user_format([msg])[0]
        return {"cmd": "message_get", "channel": channel_name, "message": msg}


async def handle_message_replies(ws, message, server_data):
    match_cmd = "message_replies"
    channel_name = message.get("channel")
    message_id = message.get("id")
    limit = message.get("limit", 50)

    if not channel_name or not message_id:
        return _error("Channel name and message ID are required", match_cmd)

    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return _error("Authentication required", match_cmd)
    
    _, error = _require_text_channel_access(user_id, channel_name)
    if error:
        return error

    replies = channels.get_message_replies(channel_name, message_id, limit)
    replies = channels.convert_messages_to_user_format(replies)
    return {"cmd": "message_replies", "channel": channel_name, "message_id": message_id, "replies": replies}
