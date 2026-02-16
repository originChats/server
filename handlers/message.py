from db import channels, users, roles
import time, uuid, sys, os, asyncio, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger
from pydantic import ValidationError
from schemas.slash_command_schema import SlashCommand
from handlers.websocket_utils import broadcast_to_voice_channel_with_viewers


def _error(error_message, match_cmd):
    """Helper function to format error responses with the command that caused them"""
    if match_cmd:
        return {"cmd": "error", "src": match_cmd, "val": error_message}
    return {"cmd": "error", "val": error_message}


def _require_user_id(ws, error_message = "User not authenticated"):
    user_id = getattr(ws, "user_id", None)
    if not user_id:
        return None, _error(error_message, None)
    return user_id, None

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

    return user_data, None

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
    user_id = getattr(ws, "user_id", None)
    if not user_id:
        return None, None, _error("Authentication required", match_cmd)
    
    if not server_data:
        return None, None, _error("Server data not available", match_cmd)
    
    voice_channels = server_data.get("voice_channels", {})
    current_channel = getattr(ws, "voice_channel", None)
    
    if not current_channel:
        return None, None, _error("You are not in a voice channel", match_cmd)
    
    if current_channel not in voice_channels:
        ws.voice_channel = None
        return None, None, _error("Voice channel no longer exists", match_cmd)
    
    if user_id not in voice_channels[current_channel]:
        ws.voice_channel = None
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
    
    await broadcast_to_voice_channel_with_viewers(
        connected_clients,
        voice_channels,
        {
            "type": event_type,
            "channel": channel_name,
            "user": user_data_with_peer
        },
        {
            "type": event_type,
            "channel": channel_name,
            "user": user_data_without_peer
        },
        channel_name
    )


async def handle(ws, message, server_data=None):
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
                content = message.get("content")
                reply_to = message.get("reply_to")  # Optional: ID of message being replied to
                user_id = getattr(ws, 'user_id', None)

                if not channel_name or not content or not user_id:
                    return _error("Invalid chat message format", match_cmd)

                content = content.strip()
                if not content:
                    return _error("Message content cannot be empty", match_cmd)

                # Check message length limit from config
                max_length = server_data.get("config", {}).get("limits", {}).get("post_content", 2000)
                if len(content) > max_length:
                    return _error(f"Message too long. Maximum length is {max_length} characters", match_cmd)

                # Check rate limiting if enabled
                if server_data and server_data.get("rate_limiter"):
                    is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
                    if not is_allowed:
                        # Convert wait time to milliseconds and send rate_limit packet
                        wait_time_ms = int(wait_time * 1000)
                        return {"cmd": "rate_limit", "reason": reason, "length": wait_time_ms}

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return _error("User roles not found", match_cmd)

                # Check if the user has permission to send messages in this channel
                if not channels.does_user_have_permission(channel_name, user_roles, "send"):
                    return _error("You do not have permission to send messages in this channel", match_cmd)

                # Validate reply_to if provided
                replied_message = None
                if reply_to:
                    replied_message = channels.get_channel_message(channel_name, reply_to)
                    if not replied_message:
                        return _error("The message you're trying to reply to was not found", match_cmd)

                # Save the message to the channel (store user ID)
                out_msg = {
                    "user": user_id,
                    "content": content,
                    "timestamp": time.time(),  # Use current timestamp
                    "type": "message",
                    "pinned": False,
                    "id": str(uuid.uuid4())
                }

                # Add reply information if this is a reply
                if reply_to and replied_message:
                    out_msg["reply_to"] = {
                        "id": reply_to,
                        "user": replied_message.get("user")
                    }

                channels.save_channel_message(channel_name, out_msg)

                # Convert message to user format before sending (user ID -> username)
                out_msg_for_client = channels.convert_messages_to_user_format([out_msg])[0]

                # Get username for plugin event
                username = users.get_username_by_id(user_id)
                
                # Trigger new_message event for plugins
                if server_data and "plugin_manager" in server_data:
                    server_data["plugin_manager"].trigger_event("new_message", ws, {
                        "content": content,
                        "channel": channel_name,
                        "user_id": user_id,
                        "username": username,
                        "message": out_msg
                    }, server_data)

                # Optionally broadcast to all clients
                return {"cmd": "message_new", "message": out_msg_for_client, "channel": channel_name, "global": True}
            case "typing":
                # Handle typing
                user_id, error = _require_user_id(ws)
                if error:
                    return error

                # Check rate limiting if enabled
                if server_data and server_data.get("rate_limiter"):
                    is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
                    if not is_allowed:
                        # Convert wait time to milliseconds and send rate_limit packet
                        wait_time_ms = int(wait_time * 1000)
                        return {"cmd": "rate_limit", "reason": reason, "wait_time": wait_time * 1000}

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
                # Handle message edit
                user_id, error = _require_user_id(ws)
                if error:
                    return error
                # Check rate limiting if enabled
                if server_data and server_data.get("rate_limiter"):
                    is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
                    if not is_allowed:
                        # Convert wait time to milliseconds and send rate_limit packet
                        wait_time_ms = int(wait_time * 1000)
                        return {"cmd": "rate_limit", "length": wait_time_ms}
                message_id = message.get("id")
                channel_name = message.get("channel")
                new_content = message.get("content")
                if not message_id or not channel_name or not new_content:
                    return _error("Invalid message edit format", match_cmd)
                # Check if the message exists
                msg_obj = channels.get_channel_message(channel_name, message_id)
                if not msg_obj:
                    return _error("Message not found or cannot be edited", match_cmd)
                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                if msg_obj.get("user") == user_id:
                    # Editing own message
                    if not channels.can_user_edit_own(channel_name, user_roles):
                        return _error("You do not have permission to edit your own message in this channel", match_cmd)
                else:
                    # Editing someone else's message (future: add edit permission if needed)
                    return _error("You do not have permission to edit this message", match_cmd)
                if not channels.edit_channel_message(channel_name, message_id, new_content):
                    return _error("Failed to edit message", match_cmd)
                if server_data:
                    username = users.get_username_by_id(user_id)
                    server_data["plugin_manager"].trigger_event("message_edit", ws, {
                        "channel": channel_name,
                        "id": message_id,
                        "content": new_content,
                        "user_id": user_id,
                        "username": username
                    }, server_data)
                
                # Get the edited message and convert to user format
                edited_msg = channels.get_channel_message(channel_name, message_id)
                if edited_msg:
                    edited_msg = channels.convert_messages_to_user_format([edited_msg])[0]
                return {"cmd": "message_edit", "id": message_id, "content": new_content, "message": edited_msg, "channel": channel_name, "global": True}
            case "message_delete":
                # Handle message delete
                user_id, error = _require_user_id(ws)
                if error:
                    return error
                
                message_id = message.get("id")
                channel_name = message.get("channel")
                if not message_id or not channel_name:
                    return _error("Invalid message delete format", match_cmd)

                # Check if the message exists and can be deleted
                message = channels.get_channel_message(channel_name, message_id)
                if not message:
                    return _error("Message not found or cannot be deleted", match_cmd)
                
                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                

                if message.get("user") == user_id:
                    # User is deleting their own message
                    if not channels.can_user_delete_own(channel_name, user_roles):
                        return _error("You do not have permission to delete your own message in this channel", match_cmd)
                else:
                    # User is deleting someone else's message
                    if not channels.does_user_have_permission(channel_name, user_roles, "delete"):
                        return _error("You do not have permission to delete this message", match_cmd)

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
                # Handle request to pin a message
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
                # Handle request to unpin a message
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
                # Convert user IDs to usernames before sending
                search_results = channels.convert_messages_to_user_format(search_results)
                return {"cmd": "messages_search", "channel": channel_name, "query": query, "results": search_results}
            case "message_react_add":
                # Handle request to add a reaction to a message
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                channel_name = message.get("channel")
                # Check if the user has permission to add reactions
                if not channels.can_user_react(channel_name, user_roles):
                    return _error("You do not have permission to add reactions to this message", match_cmd)

                message_id = message.get("id")
                if not message_id:
                    return _error("Message ID is required", match_cmd)

                emoji = message.get("emoji")
                if not emoji:
                    return _error("Emoji is required", match_cmd)

                # Store user ID, but send username to clients
                username = users.get_username_by_id(user_id)
                if not channels.add_reaction(channel_name, message_id, emoji, user_id):
                    return _error("Failed to add reaction", match_cmd)
                return {"cmd": "message_react_add", "id": message_id, "emoji": emoji, "channel": channel_name, "from": username, "global": True}
            case "message_react_remove":
                # Handle request to remove a reaction from a message
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                channel_name = message.get("channel")

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error

                # Check if the user has permission to remove reactions
                if not channels.can_user_react(channel_name, user_roles):
                    return _error("You do not have permission to remove reactions from this message", match_cmd)

                message_id = message.get("id")
                if not message_id:
                    return _error("Message ID is required", match_cmd)

                emoji = message.get("emoji")
                if not emoji:
                    return _error("Emoji is required", match_cmd)

                # Store user ID, but send username to clients
                username = users.get_username_by_id(user_id)
                if not channels.remove_reaction(channel_name, message_id, emoji, user_id):
                    return _error("Failed to remove reaction", match_cmd)
                return {"cmd": "message_react_remove", "id": message_id, "emoji": emoji, "channel": channel_name, "from": username, "global": True}
            case "messages_get":
                # Handle request for channel messages
                channel_name = message.get("channel")
                start = message.get("start", 0)
                limit = message.get("limit", 100)

                if not channel_name:
                    return _error("Invalid channel name", match_cmd)

                user_id, error = _require_user_id(ws)
                if error:
                    return error
                _, error = _require_text_channel_access(user_id, channel_name)
                if error:
                    return error

                messages = channels.get_channel_messages(channel_name, start, limit)
                # Convert user IDs to usernames before sending
                messages = channels.convert_messages_to_user_format(messages)
                return {"cmd": "messages_get", "channel": channel_name, "messages": messages}
            case "message_get":
                # Handle request for a specific message by ID
                channel_name = message.get("channel")
                message_id = message.get("id")

                if not channel_name or not message_id:
                    return _error("Channel name and message ID are required", match_cmd)

                user_id, error = _require_user_id(ws)
                if error:
                    return error
                _, error = _require_text_channel_access(user_id, channel_name)
                if error:
                    return error

                # Get the specific message
                msg = channels.get_channel_message(channel_name, message_id)
                if not msg:
                    return _error("Message not found", match_cmd)

                # Convert user ID to username before sending
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
                # Handle request for available channels
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
                        if channel.get("type") == "voice":
                            channel_name = channel.get("name")
                            if channel_name in voice_channels and user_id in voice_channels[channel_name]:
                                participants = []
                                for uid, data in voice_channels[channel_name].items():
                                    if uid != user_id:
                                        participants.append({
                                            "username": data.get("username", ""),
                                            "muted": data.get("muted", False)
                                        })
                                channel["voice_state"] = participants
                            else:
                                channel["voice_state"] = []
                
                return {"cmd": "channels_get", "val": channels_list}
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
                    user_ws = None
                    for ws in clients:
                        if getattr(ws, "user_id", None) == target_id:
                            user_ws = ws
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
                
                server_data["connected_clients"].discard(ws)  # Use discard instead of remove to avoid KeyError
                users.remove_user(user_id)
                server_data["plugin_manager"].trigger_event("user_left", ws, {
                    "user_id": user_id,
                    "username": username
                }, server_data)
                return {"cmd": "user_leave", "user": username, "val": "User left server", "global": True}
            case "users_list":
                # Handle request for all users list
                _, error = _require_user_id(ws)
                if error:
                    return error
                
                users_list = users.get_users()
                return {"cmd": "users_list", "users": users_list}
            case "users_online":
                # Handle request for online users list  
                _, error = _require_user_id(ws)
                if error:
                    return error
                
                if not server_data or "connected_clients" not in server_data:
                    return _error("Server data not available", match_cmd)
                
                # Gather authenticated users' info efficiently
                online_users = []
                for client_ws in server_data["connected_clients"]:
                    if getattr(client_ws, "authenticated", False):
                        client_user_id = getattr(client_ws, 'user_id', None)
                        if not client_user_id:
                            continue
                        user_data = users.get_user(client_user_id)
                        if not user_data:
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
                            "roles": user_data.get("roles"),
                            "color": color
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
                # Handle request for rate limit status (admin or self)
                user_id, error = _require_user_id(ws)
                if error:
                    return error
                
                target_user = message.get("user", user_id)  # Default to self
                # Resolve username to ID if needed
                target_id = users.get_id_by_username(target_user) or target_user
                user_roles, _ = _require_user_roles(user_id)
                
                # Allow users to check their own status, or admins to check anyone's
                if target_id != user_id and (not user_roles or "owner" not in user_roles):
                    return _error("Access denied: can only check your own rate limit status", match_cmd)
                
                if not server_data or not server_data.get("rate_limiter"):
                    return _error("Rate limiter not available or disabled", match_cmd)
                
                status = server_data["rate_limiter"].get_user_status(target_id)
                # Return username for display
                status_username = users.get_username_by_id(target_id)
                return {"cmd": "rate_limit_status", "user": status_username, "status": status}
            case "rate_limit_reset":
                # Handle request to reset rate limit for a user (admin only)
                user_id, error = _require_user_id(ws)
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error
                
                target_user = message.get("user")
                if not target_user:
                    return _error("User parameter is required", match_cmd)
                
                # Resolve username to ID if needed
                target_id = users.get_id_by_username(target_user) or target_user
                target_display = users.get_username_by_id(target_id)
                
                if not server_data or not server_data.get("rate_limiter"):
                    return _error("Rate limiter not available or disabled", match_cmd)
                
                server_data["rate_limiter"].reset_user(target_id)
                return {"cmd": "rate_limit_reset", "user": target_display, "val": f"Rate limit reset for user {target_display}"}
            case "slash_register":
                # Handle slash command registration
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                
                commands = message.get("commands")
                if not commands or not isinstance(commands, list):
                    return _error("Commands must be provided as a list", match_cmd)
                
                if not server_data:
                    return _error("No server data provided", match_cmd)
                
                # Validate and register each command
                for cmd in commands:
                    try:
                        validatedCommand = SlashCommand.model_validate(cmd)
                    except ValidationError as e:
                        return _error(f"Invalid command schema: {str(e)}", match_cmd)
                    
                    server_data["slash_commands"][validatedCommand.name] = validatedCommand
                    Logger.info(f"Registered slash command: {validatedCommand.name}")
                
                return {"cmd": "slash_register", "val": f"{len(commands)} commands registered successfully"}
            case "slash_list":
                # Handle request for list of slash commands
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                
                if not server_data:
                    return _error("No server data provided", match_cmd)
                
                command_lines = []
                for cmd in server_data["slash_commands"].values():
                    options_str = (
                        "\n".join(
                            f"    • {opt.name} ({opt.type})"
                            f"{' [required]' if opt.required else ''}"
                            f"{f' choices={opt.choices}' if opt.choices else ''}"
                            f": {opt.description}"
                            for opt in cmd.options
                        )
                        if cmd.options
                        else "    • No options"
                    )
                    
                    whitelist_str = (
                        f"  Whitelist roles: {', '.join(cmd.whitelistRoles)}"
                        if cmd.whitelistRoles
                        else "  Whitelist roles: None"
                    )

                    blacklist_str = (
                        f"  Blacklist roles: {', '.join(cmd.blacklistRoles)}"
                        if cmd.blacklistRoles
                        else "  Blacklist roles: None"
                    )
                    
                    ephemeral_str = f"  Ephemeral: {'Yes' if cmd.ephemeral else 'No'}"

                    command_lines.append(
                        f"/{cmd.name}\n"
                        f"  {cmd.description}\n"
                        f"{whitelist_str}\n"
                        f"{blacklist_str}\n"
                        f"{options_str}"
                        f"\n{ephemeral_str}"
                    )

                    command_lines.append(
                        f"/{cmd.name}\n"
                        f"  {cmd.description}\n"
                        f"{options_str}"
                    )

                msg = f"Registered Slash Commands ({len(command_lines)}):\n\n" + "\n\n".join(command_lines)

                return {"cmd": "slash_list", "val": msg}
            case "slash_call":
                # Handle request to call a slash command
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                
                if not server_data:
                    return _error("No server data provided", match_cmd)
                
                channel = message.get("channel")
                if not channel:
                    return _error("Channel parameter is required for slash commands", match_cmd)
                
                # Verify command existence
                cmd_name = message.get("command")
                args = message.get("args", {})
                if not isinstance(args, dict):
                    return {"cmd": "error", "val": "Command args must be an object"}

                if not isinstance(cmd_name, str):
                    return _error("Command name must be a string", match_cmd)

                command = server_data["slash_commands"].get(cmd_name)
                if not command:
                    return _error(f"Unknown slash command: /{cmd_name}", match_cmd)

                # Verify perms
                user_roles, error = _require_user_roles(user_id, requiredRoles=command.whitelistRoles or [], forbiddenRoles=command.blacklistRoles or [])
                if error:
                    return error
                
                # Verify command shape
                options = {option.name: option for option in command.options}
                
                for argument_name in args:
                    if argument_name not in options:
                        return _error(f"Unknown argument: {argument_name}", match_cmd)
                
                for option in command.options:
                    if option.required and option.name not in args:
                        return _error(f"Missing required argument: {option.name}", match_cmd)
                    
                # Validate types
                for optionName, value in args.items():
                    option = options[optionName]
                    
                    is_valid, error_message = _validate_option_value(optionName, value, option)
                    if not is_valid:
                        return {"cmd": "error", "val": error_message}

                return {"cmd": "slash_call", "val": {"command": cmd_name, "args": args}, "invoker": user_id, "channel": channel, "global": True}
            case "slash_response":
                # Handle response to a slash command
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error

                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                
                channel = message.get("channel")
                if not channel:
                    return {"cmd": "error", "val": "Channel parameter is required for slash commands"}

                response = message.get("response")
                if not isinstance(response, str):
                    return {"cmd": "error", "val": "Slash response must be a string"}

                response = response.strip()
                if not response:
                    return {"cmd": "error", "val": "Slash response cannot be empty"}

                out_msg = {
                    "user": message.get("invoker") or user_id,
                    "content": response,
                    "timestamp": time.time(),
                    "type": "message",
                    "pinned": False,
                    "id": str(uuid.uuid4())
                }

                channels.save_channel_message(channel, out_msg)
                out_msg_for_client = channels.convert_messages_to_user_format([out_msg])[0]

                return {"cmd": "slash_response", "message": out_msg_for_client, "invoker": message.get("invoker"), "channel": channel, "global": True}
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
                username = getattr(ws, "username", users.get_username_by_id(user_id))
                
                current_channel = getattr(ws, "voice_channel", None)
                if current_channel:
                    if current_channel in voice_channels and user_id in voice_channels[current_channel]:
                        await broadcast_to_voice_channel_with_viewers(
                            server_data["connected_clients"],
                            voice_channels,
                            {"type": "voice_user_left", "channel": current_channel, "username": username},
                            {"type": "voice_user_left", "channel": current_channel, "username": username},
                            current_channel
                        )
                        del voice_channels[current_channel][user_id]
                        if not voice_channels[current_channel]:
                            del voice_channels[current_channel]
                    ws.voice_channel = None
                
                if channel_name not in voice_channels:
                    voice_channels[channel_name] = {}
                
                voice_channels[channel_name][user_id] = {
                    "peer_id": peer_id,
                    "username": username,
                    "muted": False
                }
                
                ws.voice_channel = channel_name
                
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
                username = getattr(ws, "username", users.get_username_by_id(user_id))
                
                await broadcast_to_voice_channel_with_viewers(
                    server_data["connected_clients"],
                    voice_channels,
                    {"type": "voice_user_left", "channel": current_channel, "username": username},
                    {"type": "voice_user_left", "channel": current_channel, "username": username},
                    current_channel
                )
                
                del voice_channels[current_channel][user_id]
                if not voice_channels[current_channel]:
                    del voice_channels[current_channel]
                
                ws.voice_channel = None
                
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
                username = getattr(ws, "username", users.get_username_by_id(user_id))
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
            case "role_create":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                role_name = message.get("name")
                if not role_name:
                    return _error("Role name is required", match_cmd)

                role_data = {}
                if message.get("description"):
                    role_data["description"] = message["description"]
                if message.get("color"):
                    role_data["color"] = message["color"]

                if roles.role_exists(role_name):
                    return _error("Role already exists", match_cmd)

                created = roles.add_role(role_name, role_data)
                if server_data:
                    server_data["plugin_manager"].trigger_event("role_create", ws, {
                        "role_name": role_name,
                        "description": message.get("description", ""),
                        "color": message.get("color")
                    }, server_data)

                return {"cmd": "role_create", "name": role_name, "created": created}
            case "role_update":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                if not server_data:
                    return _error("Server data not available", match_cmd)
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                role_name = message.get("name")
                if not role_name:
                    return _error("Role name is required", match_cmd)

                if not roles.role_exists(role_name):
                    return _error("Role not found", match_cmd)

                role_data = roles.get_role(role_name)
                if not role_data:
                    return _error("Role not found", match_cmd)
                
                if message.get("description") is not None:
                    role_data["description"] = message["description"]
                if message.get("color") is not None:
                    role_data["color"] = message["color"]

                updated = roles.update_role(role_name, role_data)
                if server_data:
                    server_data["plugin_manager"].trigger_event("role_update", ws, {
                        "role_name": role_name,
                        "description": role_data.get("description", ""),
                        "color": role_data.get("color")
                    }, server_data)

                return {"cmd": "role_update", "name": role_name, "updated": updated}
            case "role_delete":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                role_name = message.get("name")
                if not role_name:
                    return _error("Role name is required", match_cmd)

                if not roles.role_exists(role_name):
                    return _error("Role not found", match_cmd)

                if role_name in ["owner", "admin", "user"]:
                    return _error("Cannot delete system roles", match_cmd)

                all_users = users.get_users()
                for user in all_users:
                    if role_name in user.get("roles", []):
                        return _error(f"Role is assigned to user '{user.get('username')}'", match_cmd)

                all_channels = channels.get_channels()
                for channel in all_channels:
                    perms = channel.get("permissions", {})
                    for perm_type, perm_roles in perms.items():
                        if isinstance(perm_roles, list) and role_name in perm_roles:
                            return _error(f"Role is used in channel '{channel.get('name')}' permissions", match_cmd)

                deleted = roles.delete_role(role_name)
                if server_data:
                    server_data["plugin_manager"].trigger_event("role_delete", ws, {
                        "role_name": role_name
                    }, server_data)

                return {"cmd": "role_delete", "name": role_name, "deleted": deleted}
            case "roles_list":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                all_roles = roles.get_all_roles()
                return {"cmd": "roles_list", "roles": all_roles}
            case "channel_create":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
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
                    wallpaper=message.get("wallpaper"),
                    permissions=message.get("permissions"),
                    size=message.get("size") if channel_type == "separator" else None
                )

                if created:
                    channel_data = channels.get_channel(channel_name)
                    if server_data:
                        server_data["plugin_manager"].trigger_event("channel_create", ws, {
                            "channel": channel_data
                        }, server_data)
                    return {"cmd": "channel_create", "channel": channel_data, "created": created}

                return _error("Failed to create channel", match_cmd)
            case "channel_update":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
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
            case "channel_move":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
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
            case "channel_delete":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
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
            case "user_roles_add":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                target = message.get("user")
                roles_to_add = message.get("roles")

                if not target:
                    return _error("User parameter is required", match_cmd)
                if not roles_to_add or not isinstance(roles_to_add, list):
                    return _error("Roles list is required", match_cmd)

                target_id = users.get_id_by_username(target) or target
                if not users.user_exists(target_id):
                    return _error("User not found", match_cmd)

                user_data = users.get_user(target_id)
                if not user_data:
                    return _error("User not found", match_cmd)
                user_roles = user_data.get("roles", [])

                for role in roles_to_add:
                    if role not in user_roles:
                        if not roles.role_exists(role):
                            return _error(f"Role '{role}' does not exist", match_cmd)
                        users.give_role(target_id, role)

                updated_user = users.get_user(target_id)
                username = users.get_username_by_id(target_id)
                if server_data:
                    server_data["plugin_manager"].trigger_event("user_roles_add", ws, {
                        "user_id": target_id,
                        "username": username,
                        "roles": roles_to_add
                    }, server_data)

                if not updated_user:
                    return _error("User not found", match_cmd)
                return {"cmd": "user_roles_add", "user": username, "roles": updated_user.get("roles", []), "added": True}
            case "user_roles_remove":
                user_id, error = _require_user_id(ws, "Authentication required")
                if error:
                    return error
                _, error = _require_user_roles(user_id, requiredRoles=["owner"])
                if error:
                    return error

                target = message.get("user")
                roles_to_remove = message.get("roles")

                if not target:
                    return _error("User parameter is required", match_cmd)
                if not roles_to_remove or not isinstance(roles_to_remove, list):
                    return _error("Roles list is required", match_cmd)

                target_id = users.get_id_by_username(target) or target
                if not users.user_exists(target_id):
                    return _error("User not found", match_cmd)

                user_data = users.get_user(target_id)
                if not user_data:
                    return _error("User not found", match_cmd)
                user_roles = user_data.get("roles", [])

                remaining_roles = [r for r in user_roles if r not in roles_to_remove]
                if not remaining_roles:
                    return _error("Cannot remove all roles from a user", match_cmd)

                removed = users.remove_user_roles(target_id, roles_to_remove)
                updated_user = users.get_user(target_id)
                username = users.get_username_by_id(target_id)
                if server_data and removed:
                    server_data["plugin_manager"].trigger_event("user_roles_remove", ws, {
                        "user_id": target_id,
                        "username": username,
                        "roles": roles_to_remove
                    }, server_data)

                if not updated_user:
                    return _error("User not found", match_cmd)
                return {"cmd": "user_roles_remove", "user": username, "roles": updated_user.get("roles", []), "removed": removed}
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
            case _:
                return _error(f"Unknown command: {message.get('cmd')}", match_cmd)