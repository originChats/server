import time
import uuid

from db import polls, channels, threads, users
from handlers.messages.helpers import _error, _require_user_id, _require_permission
from handlers.websocket_utils import broadcast_to_channel
from handlers.helpers.validation import validate_embeds
from schemas.embed_schema import Embed, PollData, PollOption


async def handle_poll_create(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    error = _require_permission(user_id, "send_messages", match_cmd)
    if error:
        return error

    channel = message.get("channel")
    thread_id = message.get("thread_id")
    question = message.get("question")
    options = message.get("options", [])
    allow_multiselect = message.get("allow_multiselect", False)
    expires_at = message.get("expires_at")
    duration_hours = message.get("duration_hours")

    if not user_id:
        return _error("User ID is required", match_cmd)

    if not channel and not thread_id:
        return _error("Channel or thread_id is required", match_cmd)

    if not question:
        return _error("Question is required", match_cmd)

    if not options or len(options) < 2:
        return _error("At least 2 options are required", match_cmd)

    if len(options) > 10:
        return _error("Cannot have more than 10 options", match_cmd)

    for i, opt in enumerate(options):
        if isinstance(opt, str):
            options[i] = {"id": str(i), "text": opt}
        elif isinstance(opt, dict):
            if "text" not in opt:
                return _error(f"Option {i} must have 'text'", match_cmd)
            if "id" not in opt:
                opt["id"] = str(i)

    if expires_at is None and duration_hours:
        expires_at = time.time() + (duration_hours * 3600)

    user_roles = users.get_user_roles(user_id)

    if thread_id:
        thread_data = threads.get_thread(thread_id)
        if not thread_data:
            return _error("Thread not found", match_cmd)
        parent_channel = thread_data.get("parent_channel")
        if not channels.does_user_have_permission(parent_channel, user_roles, "send"):
            return _error("You do not have permission to send messages in this thread", match_cmd)
        channel_name = parent_channel
    else:
        if not channels.channel_exists(channel):
            return _error("Channel not found", match_cmd)
        if not channels.does_user_have_permission(channel, user_roles, "send"):
            return _error("You do not have permission to send messages in this channel", match_cmd)
        channel_name = channel

    message_id = str(uuid.uuid4())
    now = time.time()

    poll_id = polls.create_poll(
        message_id=message_id,
        question=question,
        options=options,
        channel=channel,
        thread_id=thread_id,
        allow_multiselect=allow_multiselect,
        expires_at=expires_at,
        created_by=user_id
    )

    poll_embed = {
        "type": "poll",
        "poll": {
            "question": question,
            "options": options,
            "allow_multiselect": allow_multiselect,
            "expires_at": expires_at
        }
    }

    if question:
        poll_embed["title"] = question

    msg_data = {
        "id": message_id,
        "user": user_id,
        "content": "",
        "timestamp": now,
        "embeds": [poll_embed]
    }

    if thread_id:
        threads.save_thread_message(thread_id, msg_data)
    else:
        channels.save_channel_message(channel, msg_data)

    broadcast_data = {
        "cmd": "message_new",
        "id": message_id,
        "channel": channel,
        "thread_id": thread_id,
        "user": users.get_username_by_id(user_id),
        "content": "",
        "timestamp": now,
        "embeds": [poll_embed],
        "poll_id": poll_id
    }

    if server_data:
        connected_clients = server_data.get("connected_clients", set())
        if thread_id:
            await broadcast_to_channel(connected_clients, broadcast_data, channel_name, server_data)
        else:
            await broadcast_to_channel(connected_clients, broadcast_data, channel, server_data)

    return {
        "cmd": "poll_create",
        "poll_id": poll_id,
        "message_id": message_id,
        "channel": channel,
        "thread_id": thread_id,
        "question": question,
        "options": options,
        "allow_multiselect": allow_multiselect,
        "expires_at": expires_at
    }


async def handle_poll_vote(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    if not user_id:
        return _error("User ID is required", match_cmd)

    poll_id = message.get("poll_id")
    message_id = message.get("message_id")
    option_ids = message.get("option_ids") or message.get("option_id")

    if not poll_id and not message_id:
        return _error("poll_id or message_id is required", match_cmd)

    if poll_id:
        poll_data = polls.get_poll(poll_id)
    else:
        poll_data = polls.get_poll_by_message(message_id)
        if poll_data:
            poll_id = poll_data["id"]

    if not poll_data:
        return _error("Poll not found", match_cmd)

    if isinstance(option_ids, str):
        option_ids = [option_ids]

    if not option_ids:
        return _error("option_id or option_ids is required", match_cmd)

    user_roles = users.get_user_roles(user_id)

    channel = poll_data.get("channel")
    thread_id = poll_data.get("thread_id")

    if thread_id:
        thread_data = threads.get_thread(thread_id)
        if thread_data:
            parent_channel = thread_data.get("parent_channel")
            if not channels.does_user_have_permission(parent_channel, user_roles, "view"):
                return _error("You do not have permission to view this poll", match_cmd)
    elif channel:
        if not channels.does_user_have_permission(channel, user_roles, "view"):
            return _error("You do not have permission to view this poll", match_cmd)

    for option_id in option_ids:
        success, error_msg = polls.vote_poll(poll_id, option_id, user_id)
        if not success:
            return _error(error_msg, match_cmd)

    results = polls.get_poll_results(poll_id)

    vote_update = {
        "cmd": "poll_vote_update",
        "poll_id": poll_id,
        "message_id": poll_data["message_id"],
        "channel": channel,
        "thread_id": thread_id,
        "user": users.get_username_by_id(user_id),
        "option_ids": option_ids,
        "results": results
    }

    if server_data:
        connected_clients = server_data.get("connected_clients", set())
        if thread_id:
            await broadcast_to_channel(connected_clients, vote_update, channel, server_data)
        elif channel:
            await broadcast_to_channel(connected_clients, vote_update, channel, server_data)

    return {
        "cmd": "poll_vote",
        "poll_id": poll_id,
        "option_ids": option_ids,
        "results": results
    }


async def handle_poll_end(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    poll_id = message.get("poll_id")
    message_id = message.get("message_id")

    if not poll_id and not message_id:
        return _error("poll_id or message_id is required", match_cmd)

    if poll_id:
        poll_data = polls.get_poll(poll_id)
    else:
        poll_data = polls.get_poll_by_message(message_id)
        if poll_data:
            poll_id = poll_data["id"]

    if not poll_data:
        return _error("Poll not found", match_cmd)

    if poll_data["ended"]:
        return _error("Poll has already ended", match_cmd)

    if poll_data["created_by"] != user_id:
        error = _require_permission(user_id, "manage_messages", match_cmd)
        if error:
            return error

    success = polls.end_poll(poll_id)
    if not success:
        return _error("Failed to end poll", match_cmd)

    results = polls.get_poll_results(poll_id)

    end_update = {
        "cmd": "poll_end",
        "poll_id": poll_id,
        "message_id": poll_data["message_id"],
        "channel": poll_data.get("channel"),
        "thread_id": poll_data.get("thread_id"),
        "results": results
    }

    if server_data:
        connected_clients = server_data.get("connected_clients", set())
        poll_channel = poll_data.get("channel")
        if poll_data.get("thread_id"):
            await broadcast_to_channel(connected_clients, end_update, poll_channel, server_data)
        elif poll_channel:
            await broadcast_to_channel(connected_clients, end_update, poll_channel, server_data)

    return {
        "cmd": "poll_end",
        "poll_id": poll_id,
        "results": results
    }


async def handle_poll_results(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    if not user_id:
        return _error("User ID is required", match_cmd)

    poll_id = message.get("poll_id")
    message_id = message.get("message_id")

    if not poll_id and not message_id:
        return _error("poll_id or message_id is required", match_cmd)

    if poll_id:
        poll_data = polls.get_poll(poll_id)
    else:
        poll_data = polls.get_poll_by_message(message_id)
        if poll_data:
            poll_id = poll_data["id"]

    if not poll_data:
        return _error("Poll not found", match_cmd)

    user_roles = users.get_user_roles(user_id)
    channel = poll_data.get("channel")
    thread_id = poll_data.get("thread_id")

    if thread_id:
        thread_data = threads.get_thread(thread_id)
        if thread_data:
            parent_channel = thread_data.get("parent_channel")
            if not channels.does_user_have_permission(parent_channel, user_roles, "view"):
                return _error("You do not have permission to view this poll", match_cmd)
    elif channel:
        if not channels.does_user_have_permission(channel, user_roles, "view"):
            return _error("You do not have permission to view this poll", match_cmd)

    results = polls.get_poll_results(poll_id)

    if not results:
        return _error("Poll results not found", match_cmd)

    user_votes = polls.get_user_vote(poll_id, user_id)

    for result in results.get("results", []):
        result["voted"] = result["id"] in user_votes

    if results.get("ended"):
        for result in results.get("results", []):
            if result.get("voters"):
                result["voters"] = [users.get_username_by_id(uid) for uid in result["voters"]]
    else:
        for result in results.get("results", []):
            result["voters"] = []

    return {
        "cmd": "poll_results",
        "poll_id": poll_id,
        "message_id": poll_data["message_id"],
        "results": results
    }


async def handle_poll_get(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error

    if not user_id:
        return _error("User ID is required", match_cmd)

    poll_id = message.get("poll_id")
    message_id = message.get("message_id")

    if not poll_id and not message_id:
        return _error("poll_id or message_id is required", match_cmd)

    if poll_id:
        poll_data = polls.get_poll(poll_id)
    else:
        poll_data = polls.get_poll_by_message(message_id)
        if poll_data:
            poll_id = poll_data["id"]

    if not poll_data:
        return _error("Poll not found", match_cmd)

    user_roles = users.get_user_roles(user_id)
    channel = poll_data.get("channel")
    thread_id = poll_data.get("thread_id")

    if thread_id:
        thread_data = threads.get_thread(thread_id)
        if thread_data:
            parent_channel = thread_data.get("parent_channel")
            if not channels.does_user_have_permission(parent_channel, user_roles, "view"):
                return _error("You do not have permission to view this poll", match_cmd)
    elif channel:
        if not channels.does_user_have_permission(channel, user_roles, "view"):
            return _error("You do not have permission to view this poll", match_cmd)

    user_votes = polls.get_user_vote(poll_id, user_id)

    return {
        "cmd": "poll_get",
        "poll": {
            "id": poll_data["id"],
            "message_id": poll_data["message_id"],
            "channel": poll_data.get("channel"),
            "thread_id": poll_data.get("thread_id"),
            "question": poll_data["question"],
            "options": poll_data["options"],
            "allow_multiselect": poll_data["allow_multiselect"],
            "expires_at": poll_data["expires_at"],
            "created_by": users.get_username_by_id(poll_data["created_by"]),
            "created_at": poll_data["created_at"],
            "ended": poll_data["ended"],
            "ended_at": poll_data["ended_at"],
            "user_votes": user_votes
        }
    }
