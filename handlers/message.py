from db import channels, users, roles
import time, uuid, sys, os, asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger
from pydantic import ValidationError
from schemas.slash_command_schema import SlashCommand


def _require_user_id(ws, error_message = "User not authenticated"):
    user_id = getattr(ws, "user_id", None)
    if not user_id:
        return None, {"cmd": "error", "val": error_message}
    return user_id, None

def _require_user_roles(user_id, *, requiredRoles = [], forbiddenRoles = [], missing_roles_message = "User roles not found"):
    user_roles = users.get_user_roles(user_id)
    for role in requiredRoles:
        if not user_roles or role not in user_roles:
            return None, {"cmd": "error", "val": f"Access denied: '{role}' role required"}

    if not user_roles:
        return None, {"cmd": "error", "val": missing_roles_message}
    return user_roles, None

def _require_text_channel_access(user_id, channel_name):
    if not channel_name:
        return None, {"cmd": "error", "val": "Channel name not provided"}

    user_data = users.get_user(user_id)
    if not user_data:
        return None, {"cmd": "error", "val": "User not found"}

    allowed_channels = channels.get_all_channels_for_roles(user_data.get("roles", []))
    allowed_text_channel_names = [channel.get("name") for channel in allowed_channels if channel.get("type") == "text"]
    if channel_name not in allowed_text_channel_names:
        return None, {"cmd": "error", "val": "Access denied to this channel"}

    return user_data, None

def _validate_type(value, expected_type):
    match expected_type:
        case "string":
            return isinstance(value, str)
        case "int":
            return isinstance(value, int)
        case "float":
            return isinstance(value, (int, float))
        case "bool":
            return isinstance(value, bool)
        case _:
            return False



def handle(ws, message, server_data=None):
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
            return {"cmd": "error", "val": f"Invalid message format: expected a dictionary, got {type(message).__name__}"}

        match_cmd = message.get("cmd")
        match match_cmd:
            case "ping":
                # Handle ping command
                return {"cmd": "pong", "val": "pong"}
            case "message_new":
                if server_data is None:
                    return {"cmd": "error", "val": "Server data not available"}
                # Handle chat message
                channel_name = message.get("channel")
                content = message.get("content")
                reply_to = message.get("reply_to")  # Optional: ID of message being replied to
                user_id = getattr(ws, 'user_id', None)

                if not channel_name or not content or not user_id:
                    return {"cmd": "error", "val": "Invalid chat message format"}

                content = content.strip()
                if not content:
                    return {"cmd": "error", "val": "Message content cannot be empty"}

                # Check message length limit from config
                max_length = server_data.get("config", {}).get("limits", {}).get("post_content", 2000)
                if len(content) > max_length:
                    return {"cmd": "error", "val": f"Message too long. Maximum length is {max_length} characters"}

                # Check rate limiting if enabled
                if server_data and server_data.get("rate_limiter"):
                    is_allowed, reason, wait_time = server_data["rate_limiter"].is_allowed(user_id)
                    if not is_allowed:
                        # Convert wait time to milliseconds and send rate_limit packet
                        wait_time_ms = int(wait_time * 1000)
                        return {"cmd": "rate_limit", "reason": reason, "length": wait_time_ms}

                user_roles = users.get_user_roles(user_id)
                if not user_roles:
                    return {"cmd": "error", "val": "User roles not found"}

                # Check if the user has permission to send messages in this channel
                if not channels.does_user_have_permission(channel_name, user_roles, "send"):
                    return {"cmd": "error", "val": "You do not have permission to send messages in this channel"}

                # Validate reply_to if provided
                replied_message = None
                if reply_to:
                    replied_message = channels.get_channel_message(channel_name, reply_to)
                    if not replied_message:
                        return {"cmd": "error", "val": "The message you're trying to reply to was not found"}

                # Save the message to the channel (store username, not user ID)
                out_msg = {
                    "user": users.get_username_by_id(user_id),
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
                    return {"cmd": "error", "val": "Channel name not provided"}
                
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
                    return {"cmd": "error", "val": "Invalid message edit format"}
                # Check if the message exists
                msg_obj = channels.get_channel_message(channel_name, message_id)
                if not msg_obj:
                    return {"cmd": "error", "val": "Message not found or cannot be edited"}
                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                if msg_obj.get("user") == user_id:
                    # Editing own message
                    if not channels.can_user_edit_own(channel_name, user_roles):
                        return {"cmd": "error", "val": "You do not have permission to edit your own message in this channel"}
                else:
                    # Editing someone else's message (future: add edit permission if needed)
                    return {"cmd": "error", "val": "You do not have permission to edit this message"}
                if not channels.edit_channel_message(channel_name, message_id, new_content):
                    return {"cmd": "error", "val": "Failed to edit message"}
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
                    return {"cmd": "error", "val": "Invalid message delete format"}

                # Check if the message exists and can be deleted
                message = channels.get_channel_message(channel_name, message_id)
                if not message:
                    return {"cmd": "error", "val": "Message not found or cannot be deleted"}
                
                user_roles, error = _require_user_roles(user_id)
                if error:
                    return error
                

                if message.get("user") == user_id:
                    # User is deleting their own message
                    if not channels.can_user_delete_own(channel_name, user_roles):
                        return {"cmd": "error", "val": "You do not have permission to delete your own message in this channel"}
                else:
                    # User is deleting someone else's message
                    if not channels.does_user_have_permission(channel_name, user_roles, "delete"):
                        return {"cmd": "error", "val": "You do not have permission to delete this message"}

                if not channels.delete_channel_message(channel_name, message_id):
                    return {"cmd": "error", "val": "Failed to delete message"}
                
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
                    return {"cmd": "error", "val": "Channel name not provided"}
                
                if not channels.can_user_pin(channel_name, user_roles):
                    return {"cmd": "error", "val": "You do not have permission to pin messages in this channel"}

                message_id = message.get("id")
                if not message_id:
                    return {"cmd": "error", "val": "Message ID is required"}

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
                    return {"cmd": "error", "val": "Channel name not provided"}
                
                if not channels.can_user_pin(channel_name, user_roles):
                    return {"cmd": "error", "val": "You do not have permission to pin messages in this channel"}

                message_id = message.get("id")
                if not message_id:
                    return {"cmd": "error", "val": "Message ID is required"}

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
                    return {"cmd": "error", "val": "Channel name not provided"}
                
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
                    return {"cmd": "error", "val": "Channel name and query are required"}
                
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
                    return {"cmd": "error", "val": "You do not have permission to add reactions to this message"}

                message_id = message.get("id")
                if not message_id:
                    return {"cmd": "error", "val": "Message ID is required"}

                emoji = message.get("emoji")
                if not emoji:
                    return {"cmd": "error", "val": "Emoji is required"}

                # Store user ID, but send username to clients
                username = users.get_username_by_id(user_id)
                if not channels.add_reaction(channel_name, message_id, emoji, user_id):
                    return {"cmd": "error", "val": "Failed to add reaction"}
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
                    return {"cmd": "error", "val": "You do not have permission to remove reactions from this message"}

                message_id = message.get("id")
                if not message_id:
                    return {"cmd": "error", "val": "Message ID is required"}

                emoji = message.get("emoji")
                if not emoji:
                    return {"cmd": "error", "val": "Emoji is required"}

                # Store user ID, but send username to clients
                username = users.get_username_by_id(user_id)
                if not channels.remove_reaction(channel_name, message_id, emoji, user_id):
                    return {"cmd": "error", "val": "Failed to remove reaction"}
                return {"cmd": "message_react_remove", "id": message_id, "emoji": emoji, "channel": channel_name, "from": username, "global": True}
            case "messages_get":
                # Handle request for channel messages
                channel_name = message.get("channel")
                start = message.get("start", 0)
                limit = message.get("limit", 100)

                if not channel_name:
                    return {"cmd": "error", "val": "Invalid channel name"}

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
                    return {"cmd": "error", "val": "Channel name and message ID are required"}

                user_id, error = _require_user_id(ws)
                if error:
                    return error
                _, error = _require_text_channel_access(user_id, channel_name)
                if error:
                    return error

                # Get the specific message
                msg = channels.get_channel_message(channel_name, message_id)
                if not msg:
                    return {"cmd": "error", "val": "Message not found"}

                # Convert user ID to username before sending
                msg = channels.convert_messages_to_user_format([msg])[0]
                return {"cmd": "message_get", "channel": channel_name, "message": msg}
            case "message_replies":
                # Handle request for replies to a specific message
                channel_name = message.get("channel")
                message_id = message.get("id")
                limit = message.get("limit", 50)

                if not channel_name or not message_id:
                    return {"cmd": "error", "val": "Channel name and message ID are required"}

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
                    return {"cmd": "error", "val": "User not found"}
                channels_list = channels.get_all_channels_for_roles(user_data.get("roles", []))
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
                    return {"cmd": "error", "val": "Timeout must be provided"}

                if not isinstance(timeout, int):
                    return {"cmd": "error", "val": "Timeout must be a positive integer"}
                
                timeout = int(timeout)
                if timeout < 0:
                    return {"cmd": "error", "val": "Timeout must be a positive integer"}
                
                target = message.get("user")
                if not target:
                    return {"cmd": "error", "val": "User parameter is required"}

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
                    return {"cmd": "error", "val": "User parameter is required"}

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
                    return {"cmd": "error", "val": "User parameter is required"}

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
                    return {"cmd": "error", "val": "Server data not available"}
                
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
                    return {"cmd": "error", "val": "Server data not available"}
                
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
                    return {"cmd": "error", "val": "Plugin manager not available"}
                
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
                    return {"cmd": "error", "val": "Plugin manager not available"}
                
                plugin_name = message.get("plugin")
                if plugin_name:
                    # Reload specific plugin
                    success = server_data["plugin_manager"].reload_plugin(plugin_name)
                    if success:
                        return {"cmd": "plugins_reload", "val": f"Plugin '{plugin_name}' reloaded successfully"}
                    else:
                        return {"cmd": "error", "val": f"Failed to reload plugin '{plugin_name}'"}
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
                    return {"cmd": "error", "val": "Access denied: can only check your own rate limit status"}
                
                if not server_data or not server_data.get("rate_limiter"):
                    return {"cmd": "error", "val": "Rate limiter not available or disabled"}
                
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
                    return {"cmd": "error", "val": "User parameter is required"}
                
                # Resolve username to ID if needed
                target_id = users.get_id_by_username(target_user) or target_user
                target_display = users.get_username_by_id(target_id)
                
                if not server_data or not server_data.get("rate_limiter"):
                    return {"cmd": "error", "val": "Rate limiter not available or disabled"}
                
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
                    return {"cmd": "error", "val": "Commands must be provided as a list"}
                
                if not server_data:
                    return {"cmd": "error", "val": "No server data provided"}
                
                # Validate and register each command
                for cmd in commands:
                    try:
                        validatedCommand = SlashCommand.model_validate(cmd)
                    except ValidationError as e:
                        return {"cmd": "error", "val": f"Invalid command schema: {str(e)}"}
                    
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
                    return {"cmd": "error", "val": "No server data provided"}
                
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
                    return {"cmd": "error", "val": "No server data provided"}
                
                channel = message.get("channel")
                if not channel:
                    return {"cmd": "error", "val": "Channel parameter is required for slash commands"}
                
                # Verify command existence
                cmd_name = message.get("command")
                args = message.get("args", {})

                if not isinstance(cmd_name, str):
                    return {"cmd": "error", "val": "Command name must be a string"}

                command = server_data["slash_commands"].get(cmd_name)
                if not command:
                    return {"cmd": "error", "val": f"Unknown slash command: /{cmd_name}"}

                # Verify perms
                user_roles, error = _require_user_roles(user_id, requiredRoles=command.whitelistRoles or [], forbiddenRoles=command.blacklistRoles or [])
                if error:
                    return error
                
                # Verify command shape
                options = {option.name: option for option in command.options}
                
                for argument_name in args:
                    if argument_name not in options:
                        return {"cmd": "error", "val": f"Unknown argument: {argument_name}"}
                
                for option in command.options:
                    if option.required and option.name not in args:
                        return {"cmd": "error", "val": f"Missing required argument: {option.name}"}
                    
                # Validate types
                for optionName, value in args.items():
                    option = options[optionName]
                    
                    if not _validate_type(value, option.type):
                        return {"cmd": "error", "val": f"Invalid type for argument '{optionName}': expected {option.type}, got {type(value)}"}

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
                
                return {"cmd": "slash_response", "val": message.get("response"), "invoker": message.get("invoker"), "channel": channel, "global": True}
            case _:
                return {"cmd": "error", "val": f"Unknown command: {message.get('cmd')}"}
    # except Exception as e:
    #    print(f"[OriginChatsWS] Error handling message: {str(e)}")
    #    return {"cmd": "error", "val": f"Exception: {str(e)}"}
