from db import channels, users, roles, threads, permissions as perms
import asyncio
from handlers.messages.webhook import handle_webhook_create, handle_webhook_get, handle_webhook_list, handle_webhook_delete, handle_webhook_update, handle_webhook_regenerate
from handlers.messages.emoji import handle_emoji_add, handle_emoji_delete, handle_emoji_get_all, handle_emoji_update, handle_emoji_get_filename, handle_emoji_get_id
from handlers.messages.attachment import handle_attachment_delete, handle_attachment_get
from handlers.messages.role import handle_role_create, handle_role_update, handle_role_delete, handle_roles_list, handle_role_permissions_set, handle_role_permissions_get, handle_role_set, handle_role_reorder
from handlers.messages.self_role import handle_self_role_add, handle_self_role_remove, handle_self_roles_list
from handlers.messages.slash import handle_slash_register, handle_slash_list, handle_slash_call, handle_slash_response
from handlers.messages.channel import handle_channels_get, handle_channel_create, handle_channel_update, handle_channel_move, handle_channel_delete
from handlers.messages.rate_limit import handle_rate_limit_status, handle_rate_limit_reset
from handlers.messages.status import handle_status_set, handle_status_get
from handlers.messages.reaction import handle_react_add, handle_react_remove
from handlers.messages.user import handle_user_update, handle_pfp_set, handle_pfp_get
from handlers.messages.server import handle_server_update, handle_server_info
from handlers.messages.poll import handle_poll_create, handle_poll_vote, handle_poll_end, handle_poll_results, handle_poll_get
from handlers.messages.helpers import _require_permission
from handlers.messages.message import handle_message_new, handle_typing
from handlers.messages.message_edit import handle_message_edit
from handlers.messages.message_delete import handle_message_delete
from handlers.messages.message_pin import handle_message_pin, handle_message_unpin, handle_messages_pinned
from handlers.messages.messages import handle_messages_get, handle_messages_around, handle_messages_search, handle_message_get, handle_message_replies
from handlers.messages.unreads import handle_unreads_ack, handle_unreads_get, handle_unreads_count
from logger import Logger
from handlers.websocket_utils import broadcast_to_voice_channel_with_viewers, broadcast_to_all, _get_ws_attr, _set_ws_attr
from handlers import push as push_handler
from handlers.helpers.validation import (
    make_error as _error,
    require_user_id as _require_user_id,
    require_user_roles as _require_user_roles,
    get_channel_or_thread_context as _get_channel_or_thread_context,
    require_voice_channel_access as _require_voice_channel_access,
    require_voice_channel_membership as _require_voice_channel_membership,
    build_voice_participant_data as _build_voice_participant_data,
)
from handlers.helpers.thread import (
    validate_thread_access,
    validate_thread_modification,
    format_thread_for_response,
)
from handlers.helpers.mentions import (
    get_ping_patterns_for_user,
    check_ping_in_content,
)

async def _broadcast_voice_event(connected_clients, voice_channels, channel_name, event_type, user_data_with_peer, user_data_without_peer=None):
    if user_data_without_peer is None:
        user_data_without_peer = {k: v for k, v in user_data_with_peer.items() if k != "peer_id"}
    msg = {"cmd": event_type, "channel": channel_name, "user": user_data_with_peer}
    await broadcast_to_voice_channel_with_viewers(connected_clients, voice_channels, msg, msg, channel_name)


async def handle(ws, message, server_data: dict) -> dict | None:
    if not isinstance(message, dict):
        return _error(f"Invalid message format: expected a dictionary, got {type(message).__name__}", None)

    Logger.get(f"Received message: {message}")
    match_cmd = message.get("cmd")

    match match_cmd:
        case "ping":
            return {"cmd": "pong", "val": "pong"}
        case "message_new":
            return await handle_message_new(ws, message, server_data)
        case "typing":
            return await handle_typing(ws, message, server_data)
        case "message_edit":
            return await handle_message_edit(ws, message, server_data)
        case "message_delete":
            return await handle_message_delete(ws, message, server_data)
        case "message_pin":
            return await handle_message_pin(ws, message, server_data)
        case "message_unpin":
            return await handle_message_unpin(ws, message, server_data)
        case "messages_pinned":
            return await handle_messages_pinned(ws, message, server_data)
        case "messages_search":
            return await handle_messages_search(ws, message, server_data)
        case "message_react_add":
            return await handle_react_add(ws, message, match_cmd, _get_channel_or_thread_context)
        case "message_react_remove":
            return await handle_react_remove(ws, message, match_cmd, _get_channel_or_thread_context)
        case "messages_get":
            return await handle_messages_get(ws, message, server_data)
        case "messages_around":
            return await handle_messages_around(ws, message, server_data)
        case "message_get":
            return await handle_message_get(ws, message, server_data)
        case "message_replies":
            return await handle_message_replies(ws, message, server_data)
        case "channels_get":
            return handle_channels_get(ws, message, match_cmd, server_data)
        case "user_timeout":
            return await _handle_user_timeout(ws, message, match_cmd, server_data)
        case "user_ban":
            return _handle_user_ban(ws, message, match_cmd, server_data)
        case "user_unban":
            return _handle_user_unban(ws, message, match_cmd, server_data)
        case "user_leave":
            return await _handle_user_leave(ws, message, match_cmd, server_data)
        case "users_list":
            return _handle_users_list(ws, message, server_data)
        case "status_set":
            return await handle_status_set(ws, message, match_cmd, server_data)
        case "status_get":
            return await handle_status_get(ws, message, match_cmd, server_data)
        case "users_online":
            return _handle_users_online(ws, message, server_data)
        case "plugins_list":
            return _handle_plugins_list(ws, message, match_cmd, server_data)
        case "plugins_reload":
            return _handle_plugins_reload(ws, message, match_cmd, server_data)
        case "rate_limit_status":
            return await handle_rate_limit_status(ws, message, match_cmd, server_data)
        case "rate_limit_reset":
            return await handle_rate_limit_reset(ws, message, match_cmd, server_data)
        case "slash_register":
            return await handle_slash_register(ws, message, match_cmd, server_data)
        case "slash_list":
            return handle_slash_list(ws, message, match_cmd, server_data)
        case "slash_call":
            return await handle_slash_call(ws, message, match_cmd, server_data)
        case "slash_response":
            return handle_slash_response(ws, message, match_cmd, server_data)
        case "voice_join":
            return await _handle_voice_join(ws, message, match_cmd, server_data)
        case "voice_leave":
            return await _handle_voice_leave(ws, message, match_cmd, server_data)
        case "voice_mute" | "voice_unmute":
            return await _handle_voice_mute(ws, message, match_cmd, server_data)
        case "voice_state":
            return _handle_voice_state(ws, message, match_cmd, server_data)
        case "roles_list":
            return handle_roles_list(ws, message, match_cmd)
        case "role_create":
            return await handle_role_create(ws, message, match_cmd, server_data)
        case "role_update":
            return await handle_role_update(ws, message, match_cmd, server_data)
        case "role_set":
            return await handle_role_set(ws, message, match_cmd, server_data)
        case "role_delete":
            return await handle_role_delete(ws, message, match_cmd, server_data)
        case "role_reorder":
            return await handle_role_reorder(ws, message, match_cmd, server_data)
        case "role_permissions_set":
            return handle_role_permissions_set(ws, message, match_cmd)
        case "role_permissions_get":
            return await handle_role_permissions_get(ws, message, match_cmd)
        case "self_role_add":
            return await handle_self_role_add(ws, message, match_cmd, server_data)
        case "self_role_remove":
            return await handle_self_role_remove(ws, message, match_cmd, server_data)
        case "self_roles_list":
            return await handle_self_roles_list(ws, message, match_cmd)
        case "channel_create":
            return handle_channel_create(ws, message, match_cmd, server_data)
        case "channel_update":
            return handle_channel_update(ws, message, match_cmd, server_data)
        case "channel_move":
            return handle_channel_move(ws, message, match_cmd, server_data)
        case "channel_delete":
            return handle_channel_delete(ws, message, match_cmd, server_data)
        case "user_update":
            return await handle_user_update(ws, message, match_cmd, server_data)
        case "server_update":
            return await handle_server_update(ws, message, match_cmd, server_data)
        case "server_info":
            return await handle_server_info(ws, message, match_cmd)
        case "user_roles_set":
            return await _handle_user_roles_set(ws, message, match_cmd, server_data)
        case "user_roles_get":
            return _handle_user_roles_get(ws, message, match_cmd)
        case "users_banned_list":
            return _handle_users_banned_list(ws, message, match_cmd)
        case "pings_get":
            return await _handle_pings_get(ws, message, match_cmd)
        case "emoji_add":
            return await handle_emoji_add(ws, message, match_cmd)
        case "emoji_delete":
            return handle_emoji_delete(ws, message, match_cmd)
        case "emoji_get_all":
            return handle_emoji_get_all(ws, message, match_cmd)
        case "emoji_update":
            return await handle_emoji_update(ws, message, match_cmd)
        case "emoji_get_filename":
            return await handle_emoji_get_filename(ws, message, match_cmd)
        case "emoji_get_id":
            return await handle_emoji_get_id(ws, message, match_cmd)
        case "attachment_delete":
            return await handle_attachment_delete(ws, message, server_data, match_cmd)
        case "attachment_get":
            return await handle_attachment_get(ws, message, server_data, match_cmd)
        case "push_get_vapid":
            return await push_handler.handle_push_get_vapid(ws)
        case "push_subscribe":
            return await push_handler.handle_push_subscribe(ws, message)
        case "push_unsubscribe":
            return await push_handler.handle_push_unsubscribe(ws, message)
        case "thread_create":
            return _handle_thread_create(ws, message, match_cmd)
        case "thread_get":
            return _handle_thread_get(ws, message, match_cmd)
        case "thread_messages":
            return _handle_thread_messages(ws, message, match_cmd)
        case "thread_delete":
            return _handle_thread_delete(ws, message, match_cmd)
        case "thread_update":
            return _handle_thread_update(ws, message, match_cmd)
        case "thread_join":
            return _handle_thread_join(ws, message, match_cmd)
        case "thread_leave":
            return _handle_thread_leave(ws, message, match_cmd)
        case "webhook_create":
            return await handle_webhook_create(ws, message, match_cmd)
        case "webhook_get":
            return await handle_webhook_get(ws, message, match_cmd)
        case "webhook_list":
            return await handle_webhook_list(ws, message, match_cmd)
        case "webhook_delete":
            return await handle_webhook_delete(ws, message, match_cmd)
        case "webhook_update":
            return await handle_webhook_update(ws, message, match_cmd)
        case "webhook_regenerate":
            return await handle_webhook_regenerate(ws, message, match_cmd)
        case "embeds_list":
            return await _handle_embeds_list(ws, message, match_cmd)
        case "poll_create":
            return await handle_poll_create(ws, message, match_cmd, server_data)
        case "poll_vote":
            return await handle_poll_vote(ws, message, match_cmd, server_data)
        case "poll_end":
            return await handle_poll_end(ws, message, match_cmd, server_data)
        case "poll_results":
            return await handle_poll_results(ws, message, match_cmd)
        case "poll_get":
            return await handle_poll_get(ws, message, match_cmd)
        case "pfp_set":
            return await handle_pfp_set(ws, message, server_data)
        case "pfp_get":
            return await handle_pfp_get(ws, message, server_data)
        case "unreads_ack":
            return await handle_unreads_ack(ws, message, server_data)
        case "unreads_get":
            return await handle_unreads_get(ws, message, server_data)
        case "unreads_count":
            return await handle_unreads_count(ws, message, server_data)
        case _:
            return _error(f"Unknown command: {message.get('cmd')}", match_cmd)


async def _handle_user_timeout(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    timeout = message.get("timeout")
    if not timeout or not isinstance(timeout, int) or timeout < 0:
        return _error("Timeout must be a positive integer", match_cmd)
    timeout = int(timeout)

    target = message.get("user")
    if not target:
        return _error("User parameter is required", match_cmd)

    target_id = users.get_id_by_username(target) or target

    if server_data and server_data.get("rate_limiter") and server_data.get("connected_clients"):
        server_data["rate_limiter"].set_user_timeout(target_id, timeout)
        clients = server_data["connected_clients"]
        _ws_data_all = server_data.get("_ws_data", {})
        for client_ws in clients:
            client_ws_data = _ws_data_all.get(id(client_ws), {})
            if client_ws_data.get("user_id") == target_id:
                asyncio.create_task(server_data["send_to_client"](client_ws, {
                    "cmd": "rate_limit", "reason": "User timeout set", "length": timeout * 1000
                }))
                break
        if "plugin_manager" in server_data:
            server_data["plugin_manager"].trigger_event("user_timeout", ws, {
                "user_id": target_id, "username": users.get_username_by_id(target_id),
                "timeout": timeout * 1000,
            }, server_data)
    return {"cmd": "user_timeout", "user": target, "timeout": timeout}


def _handle_user_ban(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    target = message.get("user")
    if not target:
        return _error("User parameter is required", match_cmd)

    target_id = users.get_id_by_username(target) or target
    banned = users.ban_user(target_id)
    if server_data:
        server_data["plugin_manager"].trigger_event("user_ban", ws, {
            "user_id": target_id, "username": users.get_username_by_id(target_id)
        }, server_data)
    return {"cmd": "user_ban", "user": users.get_username_by_id(target_id), "banned": banned}


def _handle_user_unban(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error

    target = message.get("user")
    if not target:
        return _error("User parameter is required", match_cmd)

    target_id = users.get_id_by_username(target) or target
    unbanned = users.unban_user(target_id)
    if server_data:
        server_data["plugin_manager"].trigger_event("user_unban", ws, {
            "user_id": target_id, "username": users.get_username_by_id(target_id)
        }, server_data)
    return {"cmd": "user_unban", "user": users.get_username_by_id(target_id), "unbanned": unbanned}


async def _handle_user_leave(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    if not server_data or "connected_clients" not in server_data:
        return _error("Server data not available", match_cmd)

    username = users.get_username_by_id(user_id)
    if not users.is_user_banned(user_id):
        users.remove_user(user_id)
        Logger.success(f"User {username} (ID: {user_id}) removed from database")
    else:
        Logger.warning(f"User {username} (ID: {user_id}) is banned, keeping in database")

    await broadcast_to_all(server_data["connected_clients"], {"cmd": "user_leave", "username": username})
    if "plugin_manager" in server_data:
        server_data["plugin_manager"].trigger_event("user_leave", ws, {"username": username, "user_id": user_id}, server_data)
    return {"cmd": "user_leave", "user": username, "val": "User left server"}


def _handle_users_list(ws, message, server_data):
    _, error = _require_user_id(ws)
    if error:
        return error
    users_list = users.get_users()
    connected_usernames = server_data.get("connected_usernames", {})
    for user in users_list:
        uname = user.get("username")
        if uname not in connected_usernames or connected_usernames.get(uname, 0) <= 0:
            user["status"] = {"status": "offline", "text": user.get("status", {}).get("text", "")}
    return {"cmd": "users_list", "users": users_list}


def _handle_users_online(ws, message, server_data):
    _, error = _require_user_id(ws)
    if error:
        return error
    if not server_data or "connected_clients" not in server_data:
        return _error("Server data not available", "users_online")

    online_users = []
    _ws_data_all = server_data.get("_ws_data", {})
    for client_ws in server_data["connected_clients"]:
        client_ws_data = _ws_data_all.get(id(client_ws), {})
        if not client_ws_data.get("authenticated", False):
            continue
        client_user_id = client_ws_data.get("user_id")
        if not client_user_id:
            continue
        user_data = users.get_user(client_user_id)
        if not user_data:
            continue
        user_status = users.get_status(client_user_id)
        if user_status.get("status") == "invisible":
            continue
        user_roles = user_data.get("roles", [])
        color = roles.get_user_color(user_roles)
        username = user_data.get("username", client_user_id)
        online_users.append({
            "username": username, "nickname": user_data.get("nickname"),
            "roles": user_data.get("roles"), "color": color, "status": user_status
        })
    return {"cmd": "users_online", "users": online_users}


def _handle_plugins_list(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws)
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error
    if not server_data or "plugin_manager" not in server_data:
        return _error("Plugin manager not available", match_cmd)
    return {"cmd": "plugins_list", "plugins": server_data["plugin_manager"].get_loaded_plugins()}


def _handle_plugins_reload(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws)
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error
    if not server_data or "plugin_manager" not in server_data:
        return _error("Plugin manager not available", match_cmd)
    plugin_name = message.get("plugin")
    if plugin_name:
        success = server_data["plugin_manager"].reload_plugin(plugin_name)
        if success:
            return {"cmd": "plugins_reload", "val": f"Plugin '{plugin_name}' reloaded successfully"}
        return _error(f"Failed to reload plugin '{plugin_name}'", match_cmd)
    server_data["plugin_manager"].reload_all_plugins()
    return {"cmd": "plugins_reload", "val": "All plugins reloaded successfully"}


async def _handle_voice_join(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    channel_name = message.get("channel")
    peer_id = message.get("peer_id")
    if not peer_id:
        return _error("Peer ID is required", match_cmd)
    _, error = _require_voice_channel_access(user_id, channel_name, match_cmd)
    if error:
        return error
    if not server_data:
        return _error("Server data not available", match_cmd)

    voice_channels = server_data.get("voice_channels", {})
    _ws_data = server_data.get("_ws_data", {})
    ws_data = _ws_data.get(id(ws), {})
    username = ws_data.get("username", users.get_username_by_id(user_id))

    current_channel = ws_data.get("voice_channel")
    if current_channel and current_channel in voice_channels and user_id in voice_channels[current_channel]:
        msg = {"cmd": "voice_user_left", "channel": current_channel, "username": username}
        await broadcast_to_voice_channel_with_viewers(server_data["connected_clients"], voice_channels, msg, msg, current_channel, server_data)
        del voice_channels[current_channel][user_id]
        if not voice_channels[current_channel]:
            del voice_channels[current_channel]
        _set_ws_attr(ws, "voice_channel", None)

    if channel_name not in voice_channels:
        voice_channels[channel_name] = {}
    voice_channels[channel_name][user_id] = {"peer_id": peer_id, "username": username, "muted": False}
    _set_ws_attr(ws, "voice_channel", channel_name)

    participants = [{"username": data["username"], "peer_id": data["peer_id"], "muted": data["muted"]}
                    for uid, data in voice_channels[channel_name].items() if uid != user_id]
    await _broadcast_voice_event(server_data["connected_clients"], voice_channels, channel_name,
                                  "voice_user_joined", _build_voice_participant_data(user_id, username, peer_id, False))
    return {"cmd": "voice_join", "channel": channel_name, "participants": participants}


async def _handle_voice_leave(ws, message, match_cmd, server_data):
    user_id, current_channel, error = _require_voice_channel_membership(ws, server_data, match_cmd)
    if error:
        return error
    if not server_data:
        return _error("Server data not available", match_cmd)

    voice_channels = server_data.get("voice_channels", {})
    _ws_data = server_data.get("_ws_data", {})
    ws_data = _ws_data.get(id(ws), {})
    username = ws_data.get("username", users.get_username_by_id(user_id))

    msg = {"cmd": "voice_user_left", "channel": current_channel, "username": username}
    await broadcast_to_voice_channel_with_viewers(server_data["connected_clients"], voice_channels, msg, msg, current_channel, server_data)
    del voice_channels[current_channel][user_id]
    if not voice_channels[current_channel]:
        del voice_channels[current_channel]
    _set_ws_attr(ws, "voice_channel", None)
    return {"cmd": "voice_leave", "channel": current_channel}


async def _handle_voice_mute(ws, message, match_cmd, server_data):
    user_id, current_channel, error = _require_voice_channel_membership(ws, server_data, match_cmd)
    if error:
        return error
    if not server_data:
        return _error("Server data not available", match_cmd)

    voice_channels = server_data.get("voice_channels", {})
    muted = match_cmd == "voice_mute"
    voice_channels[current_channel][user_id]["muted"] = muted
    _ws_data = server_data.get("_ws_data", {})
    ws_data = _ws_data.get(id(ws), {})
    username = ws_data.get("username", users.get_username_by_id(user_id))
    peer_id = voice_channels[current_channel][user_id]["peer_id"]
    await _broadcast_voice_event(server_data["connected_clients"], voice_channels, current_channel,
                                  "voice_user_updated", _build_voice_participant_data(user_id, username, peer_id, muted))
    return {"cmd": match_cmd, "channel": current_channel, "muted": muted}


def _handle_voice_state(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    channel_name = message.get("channel")
    _, error = _require_voice_channel_access(user_id, channel_name, match_cmd)
    if error:
        return error
    if not server_data:
        return _error("Server data not available", match_cmd)

    voice_channels = server_data.get("voice_channels", {})
    requesting_user_in_channel = channel_name in voice_channels and user_id in voice_channels[channel_name]
    participants = []
    if channel_name in voice_channels:
        for uid, data in voice_channels[channel_name].items():
            participant = {"id": uid, "username": data["username"], "muted": data["muted"]}
            if requesting_user_in_channel:
                participant["peer_id"] = data["peer_id"]
            participants.append(participant)
    return {"cmd": "voice_state", "channel": channel_name, "participants": participants}


async def _handle_user_roles_set(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_users", match_cmd)
    if error:
        return error

    target = message.get("user")
    roles_to_set = message.get("roles")
    if not target:
        return _error("User parameter is required", match_cmd)
    if not roles_to_set or not isinstance(roles_to_set, list):
        return _error("Roles list is required", match_cmd)

    target_id = users.get_id_by_username(target) or target
    if not users.user_exists(target_id):
        return _error("User not found", match_cmd)
    for role in roles_to_set:
        if not roles.role_exists(role):
            return _error(f"Role '{role}' does not exist", match_cmd)

    users.set_user_roles(target_id, roles_to_set)
    updated_user = users.get_user(target_id)
    username = users.get_username_by_id(target_id)
    color = roles.get_user_color(roles_to_set)
    if server_data:
        server_data["plugin_manager"].trigger_event("user_roles_set", ws, {
            "user_id": target_id, "username": username, "roles": roles_to_set
        }, server_data)
    if not updated_user:
        return _error("User not found", match_cmd)
    return {"cmd": "user_roles_get", "user": username, "roles": updated_user.get("roles", []), "color": color, "global": True}


def _handle_user_roles_get(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    target = message.get("user")
    if not target:
        return _error("User parameter is required", match_cmd)
    target_id = users.get_id_by_username(target) or target
    if not users.user_exists(target_id):
        return _error("User not found", match_cmd)
    user_roles = users.get_user_roles(target_id)
    username = users.get_username_by_id(target_id)
    color = roles.get_user_color(user_roles)
    return {"cmd": "user_roles_get", "user": username, "roles": user_roles, "color": color}


def _handle_users_banned_list(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    _, error = _require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        return error
    return {"cmd": "users_banned_list", "users": users.get_banned_users()}


async def _handle_pings_get(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    user_data = users.get_user(user_id)
    if not user_data:
        return _error("User not found", match_cmd)

    limit = message.get("limit", 50)
    offset = message.get("offset", 0)
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        return _error("Limit must be a number between 1 and 100", match_cmd)
    if not isinstance(offset, int) or offset < 0:
        return _error("Offset must be a non-negative number", match_cmd)

    user_roles = user_data.get("roles", [])
    username = user_data.get("username")
    ping_patterns = get_ping_patterns_for_user(username, user_roles)

    all_channels = channels.get_channels()
    pinged_messages = []
    for channel_data in all_channels:
        if channel_data.get("type") != "text":
            continue
        channel_name = channel_data.get("name")
        if not channels.does_user_have_permission(channel_name, user_roles, "view"):
            continue
        channel_messages = channels.get_channel_messages(channel_name, 0, 10000)
        if not channel_messages:
            continue
        for msg in channel_messages:
            content = msg.get("content", "")
            is_mentioned = check_ping_in_content(content, ping_patterns)
            reply_to = msg.get("reply_to")
            is_replied = reply_to and reply_to.get("user") == user_id
            if is_replied and not msg.get("ping", True):
                continue
            if is_mentioned or is_replied:
                pinged_messages.append((msg, channel_name))

    pinged_messages.sort(key=lambda x: x[0].get("timestamp", 0), reverse=True)
    paginated = pinged_messages[offset:offset + limit]
    result = []
    for msg, ch_name in paginated:
        converted = channels.convert_messages_to_user_format([msg])[0]
        converted["channel"] = ch_name
        result.append(converted)
    return {"cmd": "pings_get", "messages": result, "offset": offset, "limit": limit, "total": len(pinged_messages)}


def _handle_thread_create(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    if not user_id:
        return _error("User ID is required", match_cmd)
    
    channel_name = message.get("channel")
    thread_name = message.get("name")
    if not channel_name or not thread_name:
        return _error("Channel and thread name are required", match_cmd)
    
    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return _error("User roles not found", match_cmd)
    
    channel_info = channels.get_channel(channel_name)
    if not channel_info:
        return _error("Channel not found", match_cmd)
    if channel_info.get("type") != "forum":
        return _error("Threads can only be created in forum channels", match_cmd)
    if not channels.does_user_have_permission(channel_name, user_roles, "create_thread"):
        return _error("You do not have permission to create threads in this channel", match_cmd)
    
    thread_name = thread_name.strip()
    if not thread_name:
        return _error("Thread name cannot be empty", match_cmd)
    
    username = users.get_username_by_id(user_id)
    thread_data = threads.create_thread(channel_name, thread_name, user_id)
    thread_data_copy = format_thread_for_response(thread_data)
    thread_data_copy["created_by"] = username
    
    return {"cmd": "thread_create", "thread": thread_data_copy, "channel": channel_name, "global": True}


def _handle_thread_get(ws, message, match_cmd):
    ctx, error = validate_thread_access(ws, message, match_cmd)
    if error or not ctx:
        return error

    thread_data = format_thread_for_response(ctx["thread_data"])
    return {"cmd": "thread_get", "thread": thread_data}


def _handle_thread_messages(ws, message, match_cmd):
    ctx, error = validate_thread_access(ws, message, match_cmd)
    if error or not ctx:
        return error

    thread_id = ctx["thread_id"]
    messages = threads.get_thread_messages(thread_id, message.get("start", 0), message.get("limit", 100))
    return {"cmd": "thread_messages", "thread_id": thread_id, "messages": threads.convert_messages_to_user_format(messages)}


def _handle_thread_delete(ws, message, match_cmd):
    ctx, error = validate_thread_modification(ws, message, match_cmd)
    if error or not ctx:
        return error

    thread_id = ctx["thread_id"]
    parent_channel = ctx["parent_channel"]
    threads.delete_thread(thread_id)

    return {"cmd": "thread_delete", "thread_id": thread_id, "channel": parent_channel, "global": True}


def _handle_thread_update(ws, message, match_cmd):
    ctx, error = validate_thread_modification(ws, message, match_cmd)
    if error or not ctx:
        return error

    thread_id = ctx["thread_id"]
    user_id = ctx["user_id"]

    can_manage = perms.has_permission(user_id, "manage_threads")

    updates = {}
    if "name" in message:
        name = message["name"].strip()
        if name:
            updates["name"] = name
        else:
            return _error("Thread name cannot be empty", match_cmd)
    if "locked" in message and can_manage:
        updates["locked"] = bool(message["locked"])
    if "archived" in message:
        updates["archived"] = bool(message["archived"])

    if updates:
        threads.update_thread(thread_id, updates)

    return {"cmd": "thread_update", "thread": threads.get_thread(thread_id), "global": True}


def _handle_thread_join(ws, message, match_cmd):
    ctx, error = validate_thread_access(ws, message, match_cmd)
    if error or not ctx:
        return error

    thread_id = ctx["thread_id"]
    user_id = ctx["user_id"]

    if threads.is_thread_locked(thread_id):
        return _error("This thread is locked", match_cmd)

    threads.join_thread(thread_id, user_id)
    updated = threads.get_thread(thread_id)
    if not updated:
        return _error("Thread not found", match_cmd)

    username = users.get_username_by_id(user_id)
    updated = format_thread_for_response(updated)

    return {"cmd": "thread_join", "thread": updated, "thread_id": thread_id, "user": username, "global": True}


def _handle_thread_leave(ws, message, match_cmd):
    ctx, error = validate_thread_access(ws, message, match_cmd, require_view_permission=False)
    if error or not ctx:
        return error

    thread_id = ctx["thread_id"]
    user_id = ctx["user_id"]

    threads.leave_thread(thread_id, user_id)
    updated = threads.get_thread(thread_id)
    if not updated:
        return _error("Thread not found", match_cmd)

    username = users.get_username_by_id(user_id)
    updated = format_thread_for_response(updated)

    return {"cmd": "thread_leave", "thread": updated, "thread_id": thread_id, "user": username, "global": True}


async def _handle_embeds_list(ws, message, match_cmd):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    message_id = message.get("id")
    channel = message.get("channel")
    thread_id = message.get("thread_id")
    if not message_id:
        return _error("Message ID is required", match_cmd)
    if not channel and not thread_id:
        return _error("Channel or thread_id is required", match_cmd)
    user_roles, error = _require_user_roles(user_id)
    if error:
        return error
    ctx, err = await _get_channel_or_thread_context(channel, thread_id, user_id, user_roles)
    if err:
        return _error(err[0], match_cmd)
    if not ctx:
        return _error("Channel or thread not found", match_cmd)
    is_thread = ctx["is_thread"]
    msg_obj = threads.get_thread_message(thread_id, message_id) if is_thread and thread_id else channels.get_channel_message(channel, message_id)
    if not msg_obj:
        return _error("Message not found", match_cmd)
    return {"cmd": "embeds_list", "id": message_id, "embeds": msg_obj.get("embeds", [])}
