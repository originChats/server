from db import channels, users, permissions as perms
from config_store import get_config_value
from handlers.websocket_utils import _get_ws_attr
from typing import TypeVar
from schemas.embed_schema import Embed, validate_embeds as schema_validate_embeds

T = TypeVar("T")


def make_error(error_message, match_cmd=None):
    if match_cmd:
        return {"cmd": "error", "src": match_cmd, "val": error_message}
    return {"cmd": "error", "val": error_message}


def config_value(server_data, *path: str, default: T) -> T:
    config = server_data.get("config") if isinstance(server_data, dict) else None
    return get_config_value(*path, default=default, config=config)


def require_user_id(ws, error_message: str = "User not authenticated"):
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return None, make_error(error_message)
    return user_id, None


def require_user_roles(user_id, *, requiredRoles=[], forbiddenRoles=[], missing_roles_message="User roles not found"):
    user_roles = users.get_user_roles(user_id)
    if forbiddenRoles and user_roles:
        for role in forbiddenRoles:
            if role in user_roles:
                return None, make_error(f"Access denied: '{role}' role is forbidden")
    for role in requiredRoles:
        if not user_roles or role not in user_roles:
            return None, make_error(f"Access denied: '{role}' role required")
    if not user_roles:
        return None, make_error(missing_roles_message)
    return user_roles, None


def check_role_permission(whitelist: list | None, blacklist: list | None, user_roles: list) -> bool:
    """
    Centralized role permission check used everywhere.
    
    Args:
        whitelist: List of allowed roles (None = no restriction)
        blacklist: List of forbidden roles (None = no restriction)
        user_roles: List of user's roles
    
    Returns:
        True if user has permission, False otherwise
    """
    if blacklist and user_roles:
        if any(role in blacklist for role in user_roles):
            return False
    if whitelist:
        if not user_roles or not any(role in whitelist for role in user_roles):
            return False
    return True


def require_owner(user_id: str, match_cmd: str) -> dict | None:
    """
    Check if user has owner role. Returns error dict if not.
    
    Args:
        user_id: User ID to check
        match_cmd: Command name for error reporting
    
    Returns:
        Error dict if not owner, None if authorized
    """
    _, error = require_user_roles(user_id, requiredRoles=["owner"])
    if error:
        error["src"] = match_cmd
    return error


def require_server_data(server_data: dict | None, match_cmd: str) -> tuple[dict | None, dict | None]:
    """
    Validate server_data is available.
    
    Args:
        server_data: Server data dict
        match_cmd: Command name for error reporting
    
    Returns:
        (server_data, error) tuple - server_data is None if unavailable
    """
    if not server_data:
        return None, make_error("Server data not available", match_cmd)
    return server_data, None


def require_permission(user_id, permission, match_cmd, channel_name=None):
    if not perms.has_permission(user_id, permission, channel_name):
        return make_error(f"Access denied: '{permission}' permission required", match_cmd)
    return None


def require_can_manage_role(actor_id, target_role, match_cmd):
    can_manage, error_msg = perms.can_manage_role(actor_id, target_role)
    if not can_manage:
        return make_error(error_msg, match_cmd)
    return None


def get_ws_username(ws):
    return _get_ws_attr(ws, "username", users.get_username_by_id(_get_ws_attr(ws, "user_id", "")))


def require_text_channel_access(user_id, channel_name):
    if not channel_name:
        return None, make_error("Channel name not provided")
    user_data = users.get_user(user_id)
    if not user_data:
        return None, make_error("User not found")
    allowed_channels = channels.get_all_channels_for_roles(user_data.get("roles", []))
    allowed_text_channel_names = [c.get("name") for c in allowed_channels if c.get("type") == "text"]
    if channel_name not in allowed_text_channel_names:
        return None, make_error("Access denied to this channel")
    channel_info = channels.get_channel(channel_name)
    if channel_info and channel_info.get("type") != "text":
        return None, make_error("Cannot use this command in this channel type")
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


async def get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles, require_send=False):
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
        return None, make_error("Channel name is required", match_cmd)
    user_data = users.get_user(user_id)
    if not user_data:
        return None, make_error("User not found", match_cmd)
    user_roles = user_data.get("roles", [])
    if not channels.does_user_have_permission(channel_name, user_roles, "view"):
        return None, make_error("You do not have permission to access this voice channel", match_cmd)
    channel_info = channels.get_channel(channel_name)
    if not channel_info or channel_info.get("type") != "voice":
        return None, make_error("This is not a voice channel", match_cmd)
    return {"user_data": user_data, "channel_info": channel_info}, None


def require_voice_channel_membership(ws, server_data, match_cmd):
    _ws_data = server_data.get("_ws_data", {}) if server_data else {}
    ws_data = _ws_data.get(id(ws), {})
    user_id = ws_data.get("user_id")
    if not user_id:
        return None, None, make_error("Authentication required", match_cmd)
    if not server_data:
        return None, None, make_error("Server data not available", match_cmd)
    voice_channels = server_data.get("voice_channels", {})
    current_channel = ws_data.get("voice_channel")
    if not current_channel:
        return None, None, make_error("You are not in a voice channel", match_cmd)
    if current_channel not in voice_channels:
        ws_data["voice_channel"] = None
        return None, None, make_error("Voice channel no longer exists", match_cmd)
    if user_id not in voice_channels[current_channel]:
        ws_data["voice_channel"] = None
        return None, None, make_error("You are not in this voice channel", match_cmd)
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


def validate_embeds(embeds: list) -> tuple[bool, str | None]:
    return schema_validate_embeds(embeds)
