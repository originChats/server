from db import channels, users, roles, serverEmojis, threads
import time, uuid, sys, os, asyncio, json, re
from handlers.messages.webhook import handle_webhook_create, handle_webhook_get, handle_webhook_list, handle_webhook_delete, handle_webhook_update, handle_webhook_regenerate
from handlers.messages.emoji import handle_emoji_add, handle_emoji_delete, handle_emoji_get_all, handle_emoji_update, handle_emoji_get_filename, handle_emoji_get_id
from handlers.messages.attachment import handle_attachment_delete, handle_attachment_get
from handlers.messages.role import handle_role_create, handle_role_update, handle_role_delete, handle_roles_list, handle_role_permissions_set, handle_role_permissions_get, handle_role_set
from handlers.messages.self_role import handle_self_role_add, handle_self_role_remove, handle_self_roles_list
from handlers.messages.slash import handle_slash_register, handle_slash_list, handle_slash_call, handle_slash_response
from handlers.messages.channel import handle_channels_get, handle_channel_create, handle_channel_update, handle_channel_move, handle_channel_delete
from handlers.messages.rate_limit import handle_rate_limit_status, handle_rate_limit_reset
from handlers.messages.status import handle_status_set, handle_status_get
from handlers.messages.reaction import handle_react_add, handle_react_remove
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger
from config_store import get_config_value
import slash_handlers
from pydantic import ValidationError
from schemas.slash_command_schema import SlashCommand
from schemas.server_emoji_schema import Emoji_add, Emoji_delete, Emoji_get_all, Emoji_update, Emoji_get_filename, Emoji_get_id
from handlers.websocket_utils import broadcast_to_voice_channel_with_viewers, broadcast_to_all, _get_ws_attr, _set_ws_attr
from handlers import push as push_handler
from handlers.helpers.validation import validate_embeds
from typing import TypeVar
import copy

T = TypeVar("T")

def _error(error_message, match_cmd):
    """Helper function to format error responses with the command that caused them"""
    if match_cmd:
        return {"cmd": "error", "src": match_cmd, "val": error_message}
    return {"cmd": "error", "val": error_message}

def _config_value(server_data, *path: str, default: T) -> T:
    config = server_data.get("config") if isinstance(server_data, dict) else None
    return get_config_value(*path, default=default, config=config)

def _require_user_id(ws, error_message: str = "User not authenticated"):
    user_id = _get_ws_attr(ws, "user_id")
    if not user_id:
        return None, _error(error_message, None)
    return user_id, None

def _get_ws_username(ws):
    return _get_ws_attr(ws, "username", users.get_username_by_id(_get_ws_attr(ws, "user_id", "")))

def _require_user_roles(user_id, *, requiredRoles = [], forbiddenRoles = [], missing_roles_message = "User roles not found"):
    user_roles = users.get_user_roles(user_id)
    for role in requiredRoles:
        if not user_roles or role not in user_roles:
            return None, _error(f"Access denied: '{role}' role required", None)

    if not user_roles:
        return None, _error(missing_roles_message, None)
    return user_roles, None

def _require_text_channel_access(user_id, channel_name):
    if not channel_name:
        return None, _error("Channel name not provided", None)

    user_data = users.get_user(user_id)
    if not user_data:
        return None, _error("User not found", None)

    allowed_channels = channels.get_all_channels_for_roles(user_data.get("roles", []))
    allowed_text_channel_names = [channel.get("name") for channel in allowed_channels if channel.get("type") == "text"]
    if channel_name not in allowed_text_channel_names:
        return None, _error("Access denied to this channel", None)

    channel_info = channels.get_channel(channel_name)
    if channel_info and channel_info.get("type") != "text":
        return None, _error("Cannot use this command in this channel type", None)

    return user_data, None


def extract_user_mentions(content, exclude_username=None):
    """Extract @username mentions from message content.
    
    Args:
        content: The message content to parse
        exclude_username: Optional username to exclude from results
        
    Returns:
        set: Set of mentioned usernames (without @ prefix)
    """
    mentioned = set(re.findall(r'@([a-zA-Z0-9_]+)', content))
    mentioned = {u for u in mentioned if not content.split(f'@{u}')[0].endswith('&')}
    if exclude_username:
        mentioned.discard(exclude_username)
    return mentioned


def extract_role_mentions(content):
    """Extract @&rolename mentions from message content.
    
    Args:
        content: The message content to parse
        
    Returns:
        set: Set of mentioned role names (without @& prefix)
    """
    return set(re.findall(r'@&([a-zA-Z0-9_]+)', content))


def extract_all_pings(content):
    """Extract all pings (user and role mentions) from message content.
    
    Args:
        content: The message content to parse
        
    Returns:
        tuple: (set of usernames, set of role names)
    """
    return extract_user_mentions(content), extract_role_mentions(content)


def get_ping_patterns_for_user(username, user_roles):
    """Generate all ping patterns that would notify a specific user.
    
    Args:
        username: The username to generate patterns for
        user_roles: List of role names the user has
        
    Returns:
        list: List of patterns to check for pings
    """
    patterns = [
        f"@{username}",
        f"@{username}@",
        f"@{username} "
    ]
    for role in user_roles:
        patterns.append(f"@&{role}")
        patterns.append(f"@&{role}@")
        patterns.append(f"@&{role} ")
    return patterns


def check_ping_in_content(content, ping_patterns):
    """Check if any ping pattern exists in content.
    
    Args:
        content: The message content to check
        ping_patterns: List of patterns to search for
        
    Returns:
        bool: True if any pattern is found in content
    """
    for pattern in ping_patterns:
        if pattern in content:
            return True
    return False


def validate_role_mentions_permissions(content, sender_user_roles):
    """Validate that the sender can mention the roles in the content.
    
    Args:
        content: The message content to validate
        sender_user_roles: List of roles the sender has
        
    Returns:
        tuple: (is_valid, error_message). is_valid is True if all role mentions are allowed.
    """
    mentioned_roles = extract_role_mentions(content)
    for mentioned_role in mentioned_roles:
        if not roles.role_exists(mentioned_role):
            continue
        if not roles.can_role_mention_role(sender_user_roles, mentioned_role):
            return False, f"You do not have permission to mention the '@&{mentioned_role}' role"
    return True, None


def get_message_pings(content, sender_user_roles):
    """Get all valid pings from message content, respecting role mention permissions.
    
    This function extracts pings from content and filters out role mentions
    that the sender doesn't have permission to use.
    
    Args:
        content: The message content to parse
        sender_user_roles: List of roles the message sender has
        
    Returns:
        dict: Contains 'users' (set of usernames) and 'roles' (set of role names)
              that were validly mentioned
    """
    mentioned_users = extract_user_mentions(content)
    mentioned_roles = extract_role_mentions(content)
    
    valid_users = set()
    for username in mentioned_users:
        user_id = users.get_id_by_username(username)
        if user_id:
            actual_username = users.get_username_by_id(user_id)
            valid_users.add(actual_username)
        else:
            valid_users.add(username)
    
    valid_roles = set()
    for role in mentioned_roles:
        if roles.role_exists(role) and roles.can_role_mention_role(sender_user_roles, role):
            valid_roles.add(role)
        elif not roles.role_exists(role):
            valid_roles.add(role)
    
    return {
        "users": list(valid_users),
        "roles": list(valid_roles),
        "replies": []
    }


def _get_thread_context(thread_id, user_id, user_roles, require_view=True):
    """Helper to validate thread access and return context. Returns (context_dict, error_response)."""
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


def _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles, require_send=False):
    """Helper to get channel/thread context. Returns (context_dict, error_response)."""
    if thread_id:
        ctx, err = _get_thread_context(thread_id, user_id, user_roles, require_view=True)
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

def _validate_type(value, expected_type):
    match expected_type:
        case "str":
            return isinstance(value, str)
        case "int":
            return isinstance(value, int) and not isinstance(value, bool)
        case "float":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        case "bool":
            return isinstance(value, bool)
        case "enum":
            return isinstance(value, str)
        case _:
            return False


def _validate_option_value(option_name, value, option):
    if not _validate_type(value, option.type):
        return False, f"Invalid type for argument '{option_name}': expected {option.type}, got {type(value).__name__}"

    if option.type == "enum":
        if not option.choices:
            return False, f"Enum argument '{option_name}' has no choices configured"
        if value not in option.choices:
            allowed_values = ", ".join(option.choices)
            return False, f"Invalid value for argument '{option_name}': expected one of [{allowed_values}], got '{value}'"

    return True, None


def _require_voice_channel_access(user_id, channel_name, match_cmd):
    if not channel_name:
        return None, _error("Channel name is required", match_cmd)
    
    user_data = users.get_user(user_id)
    if not user_data:
        return None, _error("User not found", match_cmd)
    
    user_roles = user_data.get("roles", [])
    if not channels.does_user_have_permission(channel_name, user_roles, "view"):
        return None, _error("You do not have permission to access this voice channel", match_cmd)
    
    channel_info = channels.get_channel(channel_name)
    if not channel_info or channel_info.get("type") != "voice":
        return None, _error("This is not a voice channel", match_cmd)
    
    return {"user_data": user_data, "channel_info": channel_info}, None


def _require_voice_channel_membership(ws, server_data, match_cmd):
    ws_id = id(ws)
    _ws_data = server_data.get("_ws_data", {}) if server_data else {}
    ws_data = _ws_data.get(ws_id, {})
    user_id = ws_data.get("user_id")
    if not user_id:
        return None, None, _error("Authentication required", match_cmd)

    if not server_data:
        return None, None, _error("Server data not available", match_cmd)

    voice_channels = server_data.get("voice_channels", {})
    current_channel = ws_data.get("voice_channel")

    if not current_channel:
        return None, None, _error("You are not in a voice channel", match_cmd)

    if current_channel not in voice_channels:
        ws_data["voice_channel"] = None
        return None, None, _error("Voice channel no longer exists", match_cmd)

    if user_id not in voice_channels[current_channel]:
        ws_data["voice_channel"] = None
        return None, None, _error("You are not in this voice channel", match_cmd)

    return user_id, current_channel, None


def _build_voice_participant_data(user_id, username, peer_id, muted, include_peer_id=True):
    data = {
        "id": user_id,
        "username": username,
        "muted": muted
    }
    if include_peer_id:
        data["peer_id"] = peer_id
    return data


async def _broadcast_voice_event(connected_clients, voice_channels, channel_name, event_type, user_data_with_peer, user_data_without_peer=None):
    if user_data_without_peer is None:
        user_data_without_peer = {k: v for k, v in user_data_with_peer.items() if k != "peer_id"}
    
    msg = {"cmd": event_type, "channel": channel_name, "user": user_data_with_peer}
    await broadcast_to_voice_channel_with_viewers(
        connected_clients,
        voice_channels,
        msg, msg,
        channel_name
    )


async def handle(ws, message, server_data: dict):
    """
    Handle incoming messages from clients.
    This function should be called when a new message is received.
    
    Args:
        ws: WebSocket connection
        message: Message data from client
        server_data: Dict containing server state (connected_clients, etc.)
    """
    if True:
        # Process the message here
        Logger.get(f"Received message: {message}")

        if not isinstance(message, dict):
            return _error(f"Invalid message format: expected a dictionary, got {type(message).__name__}", None)

        match_cmd = message.get("cmd")
        match match_cmd:
            case "ping":
                # Handle ping command
                return {"cmd": "pong", "val": "pong"}
            case "message_new":
                if server_data is None:
                    return _error("Server data not available", match_cmd)
                # Handle chat message
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
                    is_valid, error_msg = validate_embeds(embeds)
                    if not is_valid:
                        return _error(error_msg, match_cmd)

                # Check message length limit from config
                max_length = _config_value(server_data, "limits", "post_content", default=2000)
                if len(content) > max_length:
                    return _error(f"Message too long. Maximum length is {max_length} characters", match_cmd)

                # Check rate limiting if enabled
                if server_data and server_data.get("rate_limiter"):
                    is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
                    if not is_allowed:
                        wait_time_ms = int(wait_time * 1000)
                        return {"cmd": "rate_limit", "reason": reason, "length": wait_time_ms}

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return _error("User roles not found", match_cmd)

                # Validate role mention permissions using centralized function
                is_valid, error_msg = validate_role_mentions_permissions(content, user_roles)
                if not is_valid:
                    return _error(error_msg, match_cmd)

                # Check if the user has permission to send messages in this channel
                if thread_id:
                    thread_data = threads.get_thread(thread_id)
                    if not thread_data:
                        return _error("Thread not found", match_cmd)
                    if threads.is_thread_locked(thread_id):
                        return _error("This thread is locked", match_cmd)
                    if threads.is_thread_archived(thread_id):
                        return _error("This thread is archived", match_cmd)
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

                # Validate reply_to if provided
                replied_message = None
                if reply_to:
                    if thread_id:
                        replied_message = threads.get_thread_message(thread_id, reply_to)
                    else:
                        replied_message = channels.get_channel_message(channel_name, reply_to)
                    if not replied_message:
                        return _error("The message you're trying to reply to was not found", match_cmd)

                # Validate attachments if provided
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

                # Save the message
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
                    out_msg["reply_to"] = {
                        "id": reply_to,
                        "user": replied_message.get("user")
                    }

                ping_field = message.get("ping")
                if ping_field is not None:
                    out_msg["ping"] = bool(ping_field)

                if validated_attachments:
                    from db import attachments as attachments_db
                    att_ids = [a["id"] for a in validated_attachments]
                    attachments_db.mark_attachments_referenced(att_ids)

                if thread_id:
                    threads.save_thread_message(thread_id, out_msg)
                    out_msg_for_client = threads.convert_messages_to_user_format([out_msg])[0]
                else:
                    channels.save_channel_message(channel_name, out_msg)
                    out_msg_for_client = channels.convert_messages_to_user_format([out_msg])[0]

                if "ping" in out_msg:
                    out_msg_for_client["ping"] = out_msg["ping"]

                reply_user = None
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
                        if original_author_id and reply_user:
                            reply_author_id = original_author_id
                            if "replies" not in pings:
                                pings["replies"] = []
                            pings["replies"].append(reply_user)

                if pings.get("users") or pings.get("roles") or "replies" in pings:
                    out_msg_for_client["pings"] = pings

                if server_data and "plugin_manager" in server_data:
                    try:
                        server_data["plugin_manager"].trigger_event("new_message", ws, {
                            "content": content,
                            "channel": channel_name,
                            "user_id": user_id,
                            "username": username,
                            "message": out_msg
                        }, server_data)
                    except Exception:
                        pass

                for mentioned_username in (pings.get("users") or set()):
                    if mentioned_username == username:
                        continue

                    if server_data and not push_handler.is_user_online(mentioned_username, server_data):
                        push_handler.send_push_notification(
                            username=mentioned_username,
                            title=f"#{channel_name} \u2014 {username}",
                            body=content,
                            extra_data={"channelName": channel_name},
                        )

                for mentioned_role in (pings.get("roles") or []):
                    role_members = users.get_usernames_by_role(mentioned_role)
                    for member_username in role_members:
                        if member_username == username:
                            continue
                        if server_data and not push_handler.is_user_online(member_username, server_data):
                            push_handler.send_push_notification(
                                username=member_username,
                                title=f"#{channel_name} \u2014 {username} mentioned @{mentioned_role}",
                                body=content,
                                extra_data={"channelName": channel_name},
                            )

                if reply_to and replied_message and reply_author_id:
                    original_author = users.get_username_by_id(reply_author_id)
                    ping_flag = message.get("ping", True)
                    if ping_flag and original_author and original_author != username:
                        if not push_handler.is_user_online(original_author, server_data):
                            push_handler.send_push_notification(
                                username=original_author,
                                title=f"#{channel_name} \u2014 {username} replied",
                                body=content,
                                extra_data={"channelName": channel_name},
                            )

                if thread_id:
                    return {"cmd": "message_new", "message": out_msg_for_client, "channel": channel_name, "thread_id": thread_id, "global": True}
                else:
                    return {"cmd": "message_new", "message": out_msg_for_client, "channel": channel_name, "global": True}
            case "typing":
                user_id, error = _require_user_id(ws)
                if error:
                    return error

                if server_data and server_data.get("rate_limiter"):
                    is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
                    if not is_allowed:
                        # Convert wait time to milliseconds and send rate_limit packet
                        wait_time_ms = int(wait_time * 1000)
                        return {"cmd": "rate_limit", "reason": reason, "length": wait_time_ms}

                channel_name = message.get("channel")
                if not channel_name:
                    return _error("Channel name not provided", match_cmd)
                
                # Get username for sending to clients
                username = users.get_username_by_id(user_id)
                
                if server_data and "plugin_manager" in server_data:
                    server_data["plugin_manager"].trigger_event("typing", ws, {
                        "user_id": user_id,
                        "username": username,
                        "channel": channel_name
                    }, server_data)

                return {"cmd": "typing", "user": username, "channel": channel_name, "global": True}
            case "message_edit":
                user_id, error = _require_user_id(ws)
                if error:
                    return error

                if server_data and server_data.get("rate_limiter"):
                    is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
                    if not is_allowed:
                        wait_time_ms = int(wait_time * 1000)
                        return {"cmd": "rate_limit", "length": wait_time_ms}

                message_id = message.get("id")
                channel_name = message.get("channel")
                thread_id = message.get("thread_id")
                new_content = message.get("content")
                embeds = message.get("embeds")
                if not message_id or (not channel_name and not thread_id) or not new_content:
                    return _error("Invalid message edit format", match_cmd)

                if embeds:
                    is_valid, error_msg = validate_embeds(embeds)
                    if not is_valid:
                        return _error(error_msg, match_cmd)

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                ctx, err = _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
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
                    return _error("Message not found or cannot be edited", match_cmd)

                if msg_obj.get("user") == user_id:
                    if not channels.can_user_edit_own(parent_channel, user_roles):
                        return _error(f"You do not have permission to edit your own message in this {'thread' if is_thread else 'channel'}", match_cmd)
                else:
                    return _error("You do not have permission to edit this message", match_cmd)

                is_valid, error_msg = validate_role_mentions_permissions(new_content, user_roles)
                if not is_valid:
                    return _error(error_msg, match_cmd)

                if is_thread and thread_id:
                    if not threads.edit_thread_message(thread_id, message_id, new_content, embeds):
                        return _error("Failed to edit message", match_cmd)
                    if server_data:
                        username = users.get_username_by_id(user_id)
                        server_data["plugin_manager"].trigger_event("message_edit", ws, {
                            "channel": parent_channel,
                            "thread_id": thread_id,
                            "id": message_id,
                            "content": new_content,
                            "user_id": user_id,
                            "username": username
                        }, server_data)
                    edited_msg = threads.get_thread_message(thread_id, message_id)
                    if edited_msg:
                        edited_msg = threads.convert_messages_to_user_format([edited_msg])[0]
                        pings = get_message_pings(new_content, user_roles)
                        if pings.get("users") or pings.get("roles"):
                            edited_msg["pings"] = pings
                        if embeds:
                            edited_msg["embeds"] = embeds
                    return {"cmd": "message_edit", "id": message_id, "content": new_content, "message": edited_msg, "channel": parent_channel, "thread_id": thread_id, "global": True}
                else:
                    if not channels.edit_channel_message(channel_name, message_id, new_content, embeds):
                        return _error("Failed to edit message", match_cmd)
                    if server_data:
                        username = users.get_username_by_id(user_id)
                        server_data["plugin_manager"].trigger_event("message_edit", ws, {
                            "channel": channel_name,
                            "thread_id": thread_id,
                            "id": message_id,
                            "content": new_content,
                            "user_id": user_id,
                            "username": username
                        }, server_data)
                    edited_msg = channels.get_channel_message(channel_name, message_id)
                    if edited_msg:
                        edited_msg = channels.convert_messages_to_user_format([edited_msg])[0]
                        pings = get_message_pings(new_content, user_roles)
                        if pings.get("users") or pings.get("roles"):
                            edited_msg["pings"] = pings
                        if embeds:
                            edited_msg["embeds"] = embeds
                return {"cmd": "message_edit", "id": message_id, "content": new_content, "message": edited_msg, "channel": channel_name, "global": True}
            case "message_delete":
                user_id, error = _require_user_id(ws)
                if error:
                    return error

                message_id = message.get("id")
                channel_name = message.get("channel")
                thread_id = message.get("thread_id")
                if not message_id or (not channel_name and not thread_id):
                    return _error("Invalid message delete format", match_cmd)

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                ctx, err = _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
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
                    if server_data:
                        server_data["plugin_manager"].trigger_event("message_delete", ws, {
                            "channel": channel_name,
                            "id": message_id,
                            "user_id": user_id,
                            "username": username
                        }, server_data)
                return {"cmd": "message_delete", "id": message_id, "channel": channel_name, "global": True}
            case "message_pin":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                channel_name = message.get("channel")
                if not channel_name:
                    return _error("Channel name not provided", match_cmd)
                
                if not channels.can_user_pin(channel_name, user_roles):
                    return _error("You do not have permission to pin messages in this channel", match_cmd)

                message_id = message.get("id")
                if not message_id:
                    return _error("Message ID is required", match_cmd)

                pinned = channels.pin_channel_message(channel_name, message_id)
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
            case "message_unpin":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                channel_name = message.get("channel")
                if not channel_name:
                    return _error("Channel name not provided", match_cmd)
                
                if not channels.can_user_pin(channel_name, user_roles):
                    return _error("You do not have permission to pin messages in this channel", match_cmd)

                message_id = message.get("id")
                if not message_id:
                    return _error("Message ID is required", match_cmd)

                pinned = channels.unpin_channel_message(channel_name, message_id)
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
            case "messages_pinned":
                # Handle request for pinned messages in a channel
                channel_name = message.get("channel")
                if not channel_name:
                    return _error("Channel name not provided", match_cmd)
                
                user_id, error = _require_user_id(ws)
                if error:
                    return error
                _, error = _require_text_channel_access(user_id, channel_name)
                if error:
                    return error

                pinned_messages = channels.get_pinned_messages(channel_name)
                # Convert user IDs to usernames before sending
                pinned_messages = channels.convert_messages_to_user_format(pinned_messages)
                return {"cmd": "messages_pinned", "channel": channel_name, "messages": pinned_messages}
            case "messages_search":
                # Handle request for search results in a channel
                channel_name = message.get("channel")
                query = message.get("query")
                if not channel_name or not query:
                    return _error("Channel name and query are required", match_cmd)
                
                user_id, error = _require_user_id(ws)
                if error:
                    return error
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
                # Convert user IDs to usernames before sending
                search_results = channels.convert_messages_to_user_format(search_results)
                return {"cmd": "messages_search", "channel": channel_name, "query": query, "results": search_results}
            case "message_react_add":
                return await handle_react_add(ws, message, match_cmd, _get_channel_or_thread_context)
            case "message_react_remove":
                return await handle_react_remove(ws, message, match_cmd, _get_channel_or_thread_context)
            case "messages_get":
                channel_name = message.get("channel")
                thread_id = message.get("thread_id")
                start = message.get("start", 0)
                limit = message.get("limit", 100)
                end = start + limit

                user_id, error = _require_user_id(ws)
                if error:
                    return error
                
                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                ctx, err = _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
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
                    return {"cmd": "messages_get", "channel": parent_channel, "thread_id": thread_id, "messages": messages, "range": {"start": start, "end": end}}
                else:
                    _, error = _require_text_channel_access(user_id, channel_name)
                    if error:
                        return error
                    messages = channels.get_channel_messages(channel_name, start, limit)
                    messages = channels.convert_messages_to_user_format(messages)
                    return {"cmd": "messages_get", "channel": channel_name, "messages": messages, "range": {"start": start, "end": end}}
            case "message_get":
                channel_name = message.get("channel")
                thread_id = message.get("thread_id")
                message_id = message.get("id")

                if not message_id or (not channel_name and not thread_id):
                    return _error("Channel/thread and message ID are required", match_cmd)

                user_id, error = _require_user_id(ws)
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                ctx, err = _get_channel_or_thread_context(channel_name, thread_id, user_id, user_roles)
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
                else:
                    _, error = _require_text_channel_access(user_id, channel_name)
                    if error:
                        return error
                    msg = channels.get_channel_message(channel_name, message_id)
                    if not msg:
                        return _error("Message not found", match_cmd)
                    msg = channels.convert_messages_to_user_format([msg])[0]
                    return {"cmd": "message_get", "channel": channel_name, "message": msg}
            case "message_replies":
                # Handle request for replies to a specific message
                channel_name = message.get("channel")
                message_id = message.get("id")
                limit = message.get("limit", 50)

                if not channel_name or not message_id:
                    return _error("Channel name and message ID are required", match_cmd)

                user_id, error = _require_user_id(ws)
                if error:
                    return error
                _, error = _require_text_channel_access(user_id, channel_name)
                if error:
                    return error

                # Get replies to the message
                replies = channels.get_message_replies(channel_name, message_id, limit)
                # Convert user IDs to usernames before sending
                replies = channels.convert_messages_to_user_format(replies)
                return {"cmd": "message_replies", "channel": channel_name, "message_id": message_id, "replies": replies}
            case "channels_get":
                return handle_channels_get(ws, message, match_cmd, server_data)
            case "user_timeout":
                # Handle request to set timeout for a user
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                timeout = message.get("timeout")
                if not timeout:
                    return _error("Timeout must be provided", match_cmd)

                if not isinstance(timeout, int):
                    return _error("Timeout must be a positive integer", match_cmd)
                
                timeout = int(timeout)
                if timeout < 0:
                    return _error("Timeout must be a positive integer", match_cmd)
                
                target = message.get("user")
                if not target:
                    return _error("User parameter is required", match_cmd)

                # Try to resolve username to user ID
                target_id = users.get_id_by_username(target) or target

                if server_data and server_data.get("rate_limiter") and server_data.get("connected_clients"):
                    server_data["rate_limiter"].set_user_timeout(target_id, timeout)
                    clients = server_data["connected_clients"]
                    _ws_data_all = server_data.get("_ws_data", {})
                    user_ws = None
                    for client_ws in clients:
                        client_ws_data = _ws_data_all.get(id(client_ws), {})
                        if client_ws_data.get("user_id") == target_id:
                            user_ws = client_ws
                            break
                    if user_ws:
                        asyncio.create_task(server_data["send_to_client"](user_ws, {
                            "cmd": "rate_limit",
                            "reason": "User timeout set",
                            "length": timeout * 1000
                        }))
                    server_data["plugin_manager"].trigger_event("user_timeout", ws, {
                        "user_id": target_id,
                        "username": users.get_username_by_id(target_id),
                        "timeout": timeout * 1000,
                    }, server_data)
                return {"cmd": "user_timeout", "user": target, "timeout": timeout}
            case "user_ban":
                # Handle request to ban a user
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                target = message.get("user")
                if not target:
                    return _error("User parameter is required", match_cmd)

                # Try to resolve username to user ID
                target_id = users.get_id_by_username(target) or target

                banned = users.ban_user(target_id)
                if server_data:
                    server_data["plugin_manager"].trigger_event("user_ban", ws, {
                        "user_id": target_id,
                        "username": users.get_username_by_id(target_id)
                    }, server_data)
                # Return username for display purposes
                return {"cmd": "user_ban", "user": users.get_username_by_id(target_id), "banned": banned}
            case "user_unban":
                # Handle request to unban a user
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                target = message.get("user")
                if not target:
                    return _error("User parameter is required", match_cmd)

                # Try to resolve username to user ID
                target_id = users.get_id_by_username(target) or target

                unbanned = users.unban_user(target_id)
                if server_data:
                    server_data["plugin_manager"].trigger_event("user_unban", ws, {
                        "user_id": target_id,
                        "username": users.get_username_by_id(target_id)
                    }, server_data)
                # Return username for display purposes
                return {"cmd": "user_unban", "user": users.get_username_by_id(target_id), "unbanned": unbanned}
            case "user_leave":
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

                connected_clients = server_data["connected_clients"]
                await broadcast_to_all(connected_clients, {
                    "cmd": "user_leave",
                    "username": username
                })

                if "plugin_manager" in server_data:
                    server_data["plugin_manager"].trigger_event("user_leave", ws, {
                        "username": username,
                        "user_id": user_id
                    }, server_data)

                Logger.success(f"Broadcast user_leave: {username} left the server")

                return {"cmd": "user_leave", "user": username, "val": "User left server"}
            case "users_list":
                # Handle request for all users list
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
            case "status_set":
                return await handle_status_set(ws, message, match_cmd, server_data)
            case "status_get":
                return handle_status_get(ws, message, match_cmd, server_data)
            case "users_online":
                # Handle request for online users list
                _, error = _require_user_id(ws)
                if error:
                    return error

                if not server_data or "connected_clients" not in server_data:
                    return _error("Server data not available", match_cmd)

                # Gather authenticated users' info efficiently
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

                    # Get the color of the first role
                    user_roles = user_data.get("roles", [])
                    color = None
                    if user_roles:
                        first_role_name = user_roles[0]
                        first_role_data = roles.get_role(first_role_name)
                        if first_role_data:
                            color = first_role_data.get("color")

                    # Use the username from user data (which supports username changes)
                    username = user_data.get("username", client_user_id)
                    online_users.append({
                        "username": username,
                        "nickname": user_data.get("nickname"),
                        "roles": user_data.get("roles"),
                        "color": color,
                        "status": user_status
                    })

                return {"cmd": "users_online", "users": online_users}
            case "plugins_list":
                # Handle request for loaded plugins (admin only)
                user_id, error = _require_user_id(ws)
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error
                
                if not server_data or "plugin_manager" not in server_data:
                    return _error("Plugin manager not available", match_cmd)
                
                plugins = server_data["plugin_manager"].get_loaded_plugins()
                return {"cmd": "plugins_list", "plugins": plugins}
            case "plugins_reload":
                # Handle request to reload plugins (admin only)
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
                    # Reload specific plugin
                    success = server_data["plugin_manager"].reload_plugin(plugin_name)
                    if success:
                        return {"cmd": "plugins_reload", "val": f"Plugin '{plugin_name}' reloaded successfully"}
                    else:
                        return _error(f"Failed to reload plugin '{plugin_name}'", match_cmd)
                else:
                    # Reload all plugins
                    server_data["plugin_manager"].reload_all_plugins()
                    return {"cmd": "plugins_reload", "val": "All plugins reloaded successfully"}
            case "rate_limit_status":
                return handle_rate_limit_status(ws, message, match_cmd, server_data)
            case "rate_limit_reset":
                return handle_rate_limit_reset(ws, message, match_cmd, server_data)
            case "slash_register":
                return await handle_slash_register(ws, message, match_cmd, server_data)
            case "slash_list":
                return handle_slash_list(ws, message, match_cmd, server_data)
            case "slash_call":
                return await handle_slash_call(ws, message, match_cmd, server_data)
            case "slash_response":
                return handle_slash_response(ws, message, match_cmd, server_data)
            case "voice_join":
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
                if current_channel:
                    if current_channel in voice_channels and user_id in voice_channels[current_channel]:
                        msg = {"cmd": "voice_user_left", "channel": current_channel, "username": username}
                        await broadcast_to_voice_channel_with_viewers(
                            server_data["connected_clients"],
                            voice_channels,
                            msg, msg,
                            current_channel,
                            server_data
                        )
                        del voice_channels[current_channel][user_id]
                        if not voice_channels[current_channel]:
                            del voice_channels[current_channel]
                        _set_ws_attr(ws, "voice_channel", None)

                if channel_name not in voice_channels:
                    voice_channels[channel_name] = {}

                voice_channels[channel_name][user_id] = {
                    "peer_id": peer_id,
                    "username": username,
                    "muted": False
                }

                _set_ws_attr(ws, "voice_channel", channel_name)
                
                participants = []
                for uid, data in voice_channels[channel_name].items():
                    if uid != user_id:
                        participants.append({
                            "username": data["username"],
                            "peer_id": data["peer_id"],
                            "muted": data["muted"]
                        })
                
                await _broadcast_voice_event(
                    server_data["connected_clients"],
                    voice_channels,
                    channel_name,
                    "voice_user_joined",
                    _build_voice_participant_data(user_id, username, peer_id, False)
                )
                
                return {"cmd": "voice_join", "channel": channel_name, "participants": participants}
            
            case "voice_leave":
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
                await broadcast_to_voice_channel_with_viewers(
                    server_data["connected_clients"],
                    voice_channels,
                    msg, msg,
                    current_channel,
                    server_data
                )

                del voice_channels[current_channel][user_id]
                if not voice_channels[current_channel]:
                    del voice_channels[current_channel]

                _set_ws_attr(ws, "voice_channel", None)

                return {"cmd": "voice_leave", "channel": current_channel}

            case "voice_mute" | "voice_unmute":
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
                
                await _broadcast_voice_event(
                    server_data["connected_clients"],
                    voice_channels,
                    current_channel,
                    "voice_user_updated",
                    _build_voice_participant_data(user_id, username, peer_id, muted)
                )
                
                return {"cmd": match_cmd, "channel": current_channel, "muted": muted}
            
            case "voice_state":
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
                requesting_user_in_channel = (channel_name in voice_channels and 
                                               user_id in voice_channels[channel_name])
                
                participants = []
                if channel_name in voice_channels:
                    for uid, data in voice_channels[channel_name].items():
                        participant = {
                            "id": uid,
                            "username": data["username"],
                            "muted": data["muted"]
                        }
                        if requesting_user_in_channel:
                            participant["peer_id"] = data["peer_id"]
                        participants.append(participant)
                
                return {"cmd": "voice_state", "channel": channel_name, "participants": participants}
            case "roles_list":
                return handle_roles_list(ws, message, match_cmd)
            case "role_create":
                return handle_role_create(ws, message, match_cmd, server_data)
            case "role_update":
                return handle_role_update(ws, message, match_cmd, server_data)
            case "role_set":
                return handle_role_set(ws, message, match_cmd, server_data)
            case "role_delete":
                return handle_role_delete(ws, message, match_cmd, server_data)
            case "role_permissions_set":
                return handle_role_permissions_set(ws, message, match_cmd)
            case "role_permissions_get":
                return handle_role_permissions_get(ws, message, match_cmd)
            case "self_role_add":
                return handle_self_role_add(ws, message, match_cmd, server_data)
            case "self_role_remove":
                return handle_self_role_remove(ws, message, match_cmd, server_data)
            case "self_roles_list":
                return handle_self_roles_list(ws, message, match_cmd)
            case "channel_create":
                return handle_channel_create(ws, message, match_cmd, server_data)
            case "channel_update":
                return handle_channel_update(ws, message, match_cmd, server_data)
            case "channel_move":
                return handle_channel_move(ws, message, match_cmd, server_data)
            case "channel_delete":
                return handle_channel_delete(ws, message, match_cmd, server_data)
            case "user_roles_set":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
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

                color = None
                if roles_to_set:
                    first_role_data = roles.get_role(roles_to_set[0])
                    if first_role_data:
                        color = first_role_data.get("color")

                if server_data:
                    server_data["plugin_manager"].trigger_event("user_roles_set", ws, {
                        "user_id": target_id,
                        "username": username,
                        "roles": roles_to_set
                    }, server_data)

                if not updated_user:
                    return _error("User not found", match_cmd)
                return {"cmd": "user_roles_set", "user": username, "roles": updated_user.get("roles", []), "color": color, "set": True}
            case "user_roles_get":
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
                if not users.user_exists(target_id):
                    return _error("User not found", match_cmd)

                user_roles = users.get_user_roles(target_id)
                username = users.get_username_by_id(target_id)

                return {"cmd": "user_roles_get", "user": username, "roles": user_roles}
            case "users_banned_list":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                banned_users = users.get_banned_users()
                return {"cmd": "users_banned_list", "users": banned_users}
            case "pings_get":
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
                        is_mentioned_in_content = check_ping_in_content(content, ping_patterns)

                        is_replied_to = False
                        reply_to = msg.get("reply_to")
                        if reply_to and reply_to.get("user") == user_id:
                            is_replied_to = True

                        ping_field = msg.get("ping", True)
                        if is_replied_to and not ping_field:
                            continue

                        if is_mentioned_in_content or is_replied_to:
                            pinged_messages.append((msg, channel_name))

                pinged_messages.sort(key=lambda x: x[0].get("timestamp", 0), reverse=True)

                paginated_messages = pinged_messages[offset:offset + limit]

                result_messages = []
                for msg, channel_name in paginated_messages:
                    converted_msg = channels.convert_messages_to_user_format([msg])[0]
                    converted_msg["channel"] = channel_name
                    result_messages.append(converted_msg)

                return {
                    "cmd": "pings_get",
                    "messages": result_messages,
                    "offset": offset,
                    "limit": limit,
                    "total": len(pinged_messages)
                }
            case "emoji_add":
                return handle_emoji_add(ws, message, match_cmd)
            case "emoji_delete":
                return handle_emoji_delete(ws, message, match_cmd)
            case "emoji_get_all":
                return handle_emoji_get_all(ws, message, match_cmd)
            case "emoji_update":
                return handle_emoji_update(ws, message, match_cmd)
            case "emoji_get_filename":
                return handle_emoji_get_filename(ws, message, match_cmd)
            case "emoji_get_id":
                return handle_emoji_get_id(ws, message, match_cmd)
            case "attachment_delete":
                return handle_attachment_delete(ws, message, server_data, match_cmd)
            case "attachment_get":
                return handle_attachment_get(ws, message, server_data, match_cmd)
            case "push_get_vapid":
                return await push_handler.handle_push_get_vapid(ws)
            case "push_subscribe":
                return await push_handler.handle_push_get_vapid(ws)
            case "push_subscribe":
                return await push_handler.handle_push_subscribe(ws, message)
            case "push_unsubscribe":
                return await push_handler.handle_push_unsubscribe(ws, message)
            case "thread_create":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

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

                if not user_id:
                    return _error("User not authenticated", match_cmd)

                username = users.get_username_by_id(user_id)
                thread_data = threads.create_thread(channel_name, thread_name, user_id)

                thread_data_copy = copy.deepcopy(thread_data)
                thread_data_copy["created_by"] = username
                participant_ids = thread_data_copy.get("participants", [])
                thread_data_copy["participants"] = [users.get_username_by_id(pid) for pid in participant_ids]

                return {"cmd": "thread_create", "thread": thread_data_copy, "channel": channel_name, "global": True}
            case "thread_get":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                thread_id = message.get("thread_id")
                if not thread_id:
                    return _error("Thread ID is required", match_cmd)

                thread_data = threads.get_thread(thread_id)
                if not thread_data:
                    return _error("Thread not found", match_cmd)

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return _error("User roles not found", match_cmd)

                if not channels.does_user_have_permission(thread_data.get("parent_channel"), user_roles, "view"):
                    return _error("You do not have permission to view this thread", match_cmd)

                thread_data["created_by"] = users.get_username_by_id(thread_data.get("created_by"))
                participant_ids = thread_data.get("participants", [])
                thread_data["participants"] = [users.get_username_by_id(pid) for pid in participant_ids]
                return {"cmd": "thread_get", "thread": thread_data}
            case "thread_messages":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                thread_id = message.get("thread_id")
                start = message.get("start", 0)
                limit = message.get("limit", 100)

                if not thread_id:
                    return _error("Thread ID is required", match_cmd)

                thread_data = threads.get_thread(thread_id)
                if not thread_data:
                    return _error("Thread not found", match_cmd)

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return _error("User roles not found", match_cmd)

                if not channels.does_user_have_permission(thread_data.get("parent_channel"), user_roles, "view"):
                    return _error("You do not have permission to view this thread", match_cmd)

                messages = threads.get_thread_messages(thread_id, start, limit)
                converted_messages = threads.convert_messages_to_user_format(messages)

                return {"cmd": "thread_messages", "thread_id": thread_id, "messages": converted_messages}
            case "thread_delete":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                thread_id = message.get("thread_id")
                if not thread_id:
                    return _error("Thread ID is required", match_cmd)

                thread_data = threads.get_thread(thread_id)
                if not thread_data:
                    return _error("Thread not found", match_cmd)

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return _error("User roles not found", match_cmd)

                is_owner = thread_data.get("created_by") == user_id
                is_admin = "owner" in user_roles or "admin" in user_roles

                if not is_owner and not is_admin:
                    return _error("You do not have permission to delete this thread", match_cmd)

                threads.delete_thread(thread_id)
                return {"cmd": "thread_delete", "thread_id": thread_id, "channel": thread_data.get("parent_channel"), "global": True}
            case "thread_update":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                thread_id = message.get("thread_id")
                if not thread_id:
                    return _error("Thread ID is required", match_cmd)

                thread_data = threads.get_thread(thread_id)
                if not thread_data:
                    return _error("Thread not found", match_cmd)

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return _error("User roles not found", match_cmd)

                is_owner = thread_data.get("created_by") == user_id
                is_admin = "owner" in user_roles or "admin" in user_roles

                if not is_owner and not is_admin:
                    return _error("You do not have permission to update this thread", match_cmd)

                updates = {}
                if "name" in message:
                    name = message["name"].strip()
                    if name:
                        updates["name"] = name
                    else:
                        return _error("Thread name cannot be empty", match_cmd)
                if "locked" in message and is_admin:
                    updates["locked"] = bool(message["locked"])
                if "archived" in message:
                    updates["archived"] = bool(message["archived"])

                if updates:
                    threads.update_thread(thread_id, updates)

                updated_thread = threads.get_thread(thread_id)
                return {"cmd": "thread_update", "thread": updated_thread, "global": True}
            case "thread_join":
                user_id, error = _require_user_id(ws, "Authentication required")
                if not user_id or error:
                    return error

                thread_id = message.get("thread_id")
                if not thread_id:
                    return _error("Thread ID is required", match_cmd)

                thread_data = threads.get_thread(thread_id)
                if not thread_data:
                    return _error("Thread not found", match_cmd)

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return _error("User roles not found", match_cmd)

                if not channels.does_user_have_permission(thread_data.get("parent_channel"), user_roles, "view"):
                    return _error("You do not have permission to join this thread", match_cmd)

                if threads.is_thread_locked(thread_id):
                    return _error("This thread is locked", match_cmd)

                if threads.is_thread_archived(thread_id):
                    return _error("This thread is archived", match_cmd)

                threads.join_thread(thread_id, user_id)
                updated_thread = threads.get_thread(thread_id)
                if not updated_thread:
                    return _error("Thread not found", match_cmd)
                username = users.get_username_by_id(user_id)
                participant_ids = updated_thread.get("participants", [])
                updated_thread["participants"] = [users.get_username_by_id(pid) for pid in participant_ids]

                return {"cmd": "thread_join", "thread": updated_thread, "thread_id": thread_id, "user": username, "global": True}
            case "thread_leave":
                user_id, error = _require_user_id(ws, "Authentication required")
                if not user_id or error:
                    return error

                thread_id = message.get("thread_id")
                if not thread_id:
                    return _error("Thread ID is required", match_cmd)

                thread_data = threads.get_thread(thread_id)
                if not thread_data:
                    return _error("Thread not found", match_cmd)

                threads.leave_thread(thread_id, user_id)
                updated_thread = threads.get_thread(thread_id)
                if not updated_thread:
                    return _error("Thread not found", match_cmd)
                username = users.get_username_by_id(user_id)
                participant_ids = updated_thread.get("participants", [])
                updated_thread["participants"] = [users.get_username_by_id(pid) for pid in participant_ids]

                return {"cmd": "thread_leave", "thread": updated_thread, "thread_id": thread_id, "user": username, "global": True}
            case "webhook_create":
                return handle_webhook_create(ws, message, match_cmd)
            case "webhook_get":
                return handle_webhook_get(ws, message, match_cmd)
            case "webhook_list":
                return handle_webhook_list(ws, message, match_cmd)
            case "webhook_delete":
                return handle_webhook_delete(ws, message, match_cmd)
            case "webhook_update":
                return handle_webhook_update(ws, message, match_cmd)
            case "webhook_regenerate":
                return handle_webhook_regenerate(ws, message, match_cmd)
            case "embeds_list":
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

                ctx, err = _get_channel_or_thread_context(channel, thread_id, user_id, user_roles)
                if err:
                    msg, key = err
                    return _error(msg, match_cmd)

                if not ctx:
                    return _error("Channel or thread not found", match_cmd)

                is_thread = ctx["is_thread"]

                if is_thread and thread_id:
                    msg_obj = threads.get_thread_message(thread_id, message_id)
                else:
                    msg_obj = channels.get_channel_message(channel, message_id)

                if not msg_obj:
                    return _error("Message not found", match_cmd)

                embeds = msg_obj.get("embeds", [])

                return {"cmd": "embeds_list", "id": message_id, "embeds": embeds}
            case _:
                return _error(f"Unknown command: {message.get('cmd')}", match_cmd)
