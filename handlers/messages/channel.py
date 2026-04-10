from db import channels, users, threads
from handlers.messages.helpers import _error, _require_user_id, _require_permission


def handle_channels_get(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws)
    if error:
        return error
    user_data = users.get_user(user_id)
    if not user_data:
        return _error("User not found", match_cmd)
    channels_list = channels.get_all_channels_for_roles(user_data.get("roles", []))

    if server_data:
        voice_channels = server_data.get("voice_channels", {})
        for channel in channels_list:
            if channel.get("type") == "text":
                channel_name = channel.get("name")
                msgs = channels.get_channel_messages(channel_name, 0, 1)
                msg = msgs[0] if msgs else {}
                channel["last_message"] = msg.get("timestamp")
                channel["last_message_id"] = msg.get("id")
            elif channel.get("type") == "voice":
                channel_name = channel.get("name")
                participants = []
                for uid, data in voice_channels.get(channel_name, {}).items():
                    participants.append({
                        "username": data.get("username", ""),
                        "muted": data.get("muted", False)
                    })
                channel["voice_state"] = participants
            elif channel.get("type") == "forum":
                channel_name = channel.get("name")
                channel_threads = threads.get_channel_threads(channel_name)
                for thread in channel_threads:
                    if "participants" in thread:
                        thread["participants"] = [users.get_username_by_id(pid) for pid in thread["participants"]]
                    if "created_by" in thread:
                        thread["created_by"] = users.get_username_by_id(thread["created_by"]) or thread["created_by"]
                channel["threads"] = channel_threads

    return {"cmd": "channels_get", "val": channels_list}


def handle_channel_create(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_channels", match_cmd)
    if error:
        return error

    channel_name = message.get("name")
    channel_type = message.get("type")

    if not channel_name:
        return _error("Channel name is required", match_cmd)
    if not channel_type:
        return _error("Channel type is required (text, voice, or separator)", match_cmd)
    if channel_type not in ["text", "voice", "separator"]:
        return _error("Invalid channel type, must be text, voice, or separator", match_cmd)

    if channels.channel_exists(channel_name):
        return _error("Channel already exists", match_cmd)

    created = channels.create_channel(
        channel_name,
        channel_type,
        description=message.get("description"),
        display_name=message.get("display_name"),
        permissions=message.get("permissions"),
        size=(message.get("size") or None) if channel_type == "separator" else None
    )

    if created:
        channel_data = channels.get_channel(channel_name)
        if server_data:
            server_data["plugin_manager"].trigger_event("channel_create", ws, {
                "channel": channel_data
            }, server_data)
        return {"cmd": "channel_create", "channel": channel_data, "created": created}

    return _error("Failed to create channel", match_cmd)


def handle_channel_update(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_channels", match_cmd)
    if error:
        return error

    current_name = message.get("current_name")
    updates = message.get("updates")

    if not current_name:
        return _error("current_name is required", match_cmd)
    if not updates or not isinstance(updates, dict):
        return _error("updates object is required", match_cmd)

    if not channels.channel_exists(current_name):
        return _error("Channel not found", match_cmd)

    if "type" in updates and updates["type"] not in ["text", "voice", "separator"]:
        return _error("Invalid channel type", match_cmd)

    if "name" in updates and updates["name"] != current_name:
        if channels.channel_exists(updates["name"]):
            return _error("Channel with new name already exists", match_cmd)

    updated = channels.update_channel(current_name, updates)
    if updated:
        channel = channels.get_channel(updates.get("name", current_name))
        if server_data:
            server_data["plugin_manager"].trigger_event("channel_update", ws, {
                "old_name": current_name,
                "channel": channel
            }, server_data)
        return {"cmd": "channel_update", "channel": channel, "updated": updated}

    return _error("Failed to update channel", match_cmd)


def handle_channel_move(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_channels", match_cmd)
    if error:
        return error

    channel_name = message.get("name")
    new_position = message.get("position")

    if not channel_name:
        return _error("Channel name is required", match_cmd)
    if new_position is None:
        return _error("Position is required", match_cmd)

    if not isinstance(new_position, int) or new_position < 0:
        return _error("Position must be a non-negative integer", match_cmd)

    moved = channels.reorder_channel(channel_name, new_position)
    if server_data and moved:
        channel = channels.get_channel(channel_name)
        server_data["plugin_manager"].trigger_event("channel_move", ws, {
            "channel": channel,
            "position": new_position
        }, server_data)

    return {"cmd": "channel_move", "name": channel_name, "position": new_position, "moved": moved}


def handle_channel_delete(ws, message, match_cmd, server_data):
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return error
    error = _require_permission(user_id, "manage_channels", match_cmd)
    if error:
        return error

    channel_name = message.get("name")
    if not channel_name:
        return _error("Channel name is required", match_cmd)

    if not channels.channel_exists(channel_name):
        channel_name_lower = channel_name.lower()
        all_channels = channels.get_channels()
        for channel in all_channels:
            if channel.get("name", "").lower() == channel_name_lower:
                channel_name = channel.get("name")
                break
        else:
            return _error("Channel not found", match_cmd)

    deleted = channels.delete_channel(channel_name)
    if server_data and deleted:
        server_data["plugin_manager"].trigger_event("channel_delete", ws, {
            "channel_name": channel_name
        }, server_data)

    return {"cmd": "channel_delete", "name": channel_name, "deleted": deleted}
