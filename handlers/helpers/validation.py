from db import channels, users
from config_store import get_config_value
from typing import TypeVar

T = TypeVar("T")


def error(error_message, match_cmd=None):
    if match_cmd:
        return {"cmd": "error", "src": match_cmd, "val": error_message}
    return {"cmd": "error", "val": error_message}


def config_value(server_data, *path: str, default: T) -> T:
    config = server_data.get("config") if isinstance(server_data, dict) else None
    return get_config_value(*path, default=default, config=config)


def require_user_id(ws, error_message="User not authenticated"):
    user_id = getattr(ws, "user_id", None)
    if not user_id:
        return None, error(error_message)
    return user_id, None


def require_user_roles(user_id, *, requiredRoles=[], forbiddenRoles=[], missing_roles_message="User roles not found"):
    user_roles = users.get_user_roles(user_id)
    for role in requiredRoles:
        if not user_roles or role not in user_roles:
            return None, error(f"Access denied: '{role}' role required")
    if not user_roles:
        return None, error(missing_roles_message)
    return user_roles, None


def require_text_channel_access(user_id, channel_name):
    if not channel_name:
        return None, error("Channel name not provided")
    user_data = users.get_user(user_id)
    if not user_data:
        return None, error("User not found")
    allowed_channels = channels.get_all_channels_for_roles(user_data.get("roles", []))
    allowed_text_channel_names = [c.get("name") for c in allowed_channels if c.get("type") == "text"]
    if channel_name not in allowed_text_channel_names:
        return None, error("Access denied to this channel")
    channel_info = channels.get_channel(channel_name)
    if channel_info and channel_info.get("type") != "text":
        return None, error("Cannot use this command in this channel type")
    return user_data, None


def get_thread_context(thread_id, user_id, user_roles, require_view=True):
    from db import threads
    thread_data = threads.get_thread(thread_id)
    if not thread_data:
        return None, ("Thread not found", "thread_id")
    if threads.is_thread_locked(thread_id):
        return None, ("This thread is locked", "thread_id")
    if threads.is_thread_archived(thread_id):
        return None, ("This thread is archived", "thread_id")
    parent_channel = thread_data.get("parent_channel")
    if require_view:
        if not channels.does_user_have_permission(parent_channel, user_roles, "view"):
            return None, ("You do not have permission to view this thread", "thread_id")
    return {"thread": thread_data, "parent_channel": parent_channel}, None


def get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles, require_send=False):
    if thread_id:
        ctx, err = get_thread_context(thread_id, user_id, user_roles, require_view=True)
        if err:
            return None, err
        if not ctx:
            return None, ("Thread not found", "thread")
        ctx["is_thread"] = True
        return ctx, None
    elif channel_name:
        if not channels.channel_exists(channel_name):
            return None, ("Channel not found", "channel")
        if require_send:
            if not channels.does_user_have_permission(channel_name, user_roles, "send"):
                return None, ("You do not have permission to send messages in this channel", "channel")
        return {"channel": channel_name, "is_thread": False}, None
    else:
        return None, ("Channel or thread_id required", "channel")


def require_voice_channel_access(user_id, channel_name, match_cmd):
    if not channel_name:
        return None, error("Channel name is required", match_cmd)
    user_data = users.get_user(user_id)
    if not user_data:
        return None, error("User not found", match_cmd)
    user_roles = user_data.get("roles", [])
    if not channels.does_user_have_permission(channel_name, user_roles, "view"):
        return None, error("You do not have permission to access this voice channel", match_cmd)
    channel_info = channels.get_channel(channel_name)
    if not channel_info or channel_info.get("type") != "voice":
        return None, error("This is not a voice channel", match_cmd)
    return {"user_data": user_data, "channel_info": channel_info}, None


def require_voice_channel_membership(ws, server_data, match_cmd):
    user_id = getattr(ws, "user_id", None)
    if not user_id:
        return None, None, error("Authentication required", match_cmd)
    if not server_data:
        return None, None, error("Server data not available", match_cmd)
    voice_channels = server_data.get("voice_channels", {})
    current_channel = getattr(ws, "voice_channel", None)
    if not current_channel:
        return None, None, error("You are not in a voice channel", match_cmd)
    if current_channel not in voice_channels:
        ws.voice_channel = None
        return None, None, error("Voice channel no longer exists", match_cmd)
    if user_id not in voice_channels[current_channel]:
        ws.voice_channel = None
        return None, None, error("You are not in this voice channel", match_cmd)
    return user_id, current_channel, None


def build_voice_participant_data(user_id, username, peer_id, muted, include_peer_id=True):
    data = {"id": user_id, "username": username, "muted": muted}
    if include_peer_id:
        data["peer_id"] = peer_id
    return data


def validate_type(value, expected_type):
    match expected_type:
        case "str": return isinstance(value, str)
        case "int": return isinstance(value, int) and not isinstance(value, bool)
        case "float": return isinstance(value, (int, float)) and not isinstance(value, bool)
        case "bool": return isinstance(value, bool)
        case "enum": return isinstance(value, str)
        case _: return False


def validate_option_value(option_name, value, option):
    if not validate_type(value, option.type):
        return False, f"Invalid type for argument '{option_name}': expected {option.type}, got {type(value).__name__}"
    if option.type == "enum":
        if not option.choices:
            return False, f"Enum argument '{option_name}' has no choices configured"
        if value not in option.choices:
            allowed_values = ", ".join(option.choices)
            return False, f"Invalid value for argument '{option_name}': expected one of [{allowed_values}], got '{value}'"
    return True, None
