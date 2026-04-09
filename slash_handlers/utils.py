from db import users
from handlers.websocket_utils import disconnect_user, _get_ws_attr
from logger import Logger
from typing import Tuple, Dict, Any, Optional


def validate_target_user(username: str) -> Tuple[Optional[str], Optional[Dict], Optional[Dict]]:
    """
    Validate and lookup a target user by username.
    
    Returns:
        (target_id, target_user, error_response)
        - target_id: The user ID if found, None if not
        - target_user: The user data dict if found, None if not
        - error_response: Error dict if validation failed, None if success
    """
    if not username:
        return None, None, {"error": "Username is required"}
    
    target_id = users.get_id_by_username(username)
    if not target_id:
        return None, None, {"error": f"User '{username}' not found"}
    
    target_user = users.get_user(target_id)
    return target_id, target_user, None


def check_can_modify_target(target_user: Optional[Dict], action_name: str = "modify") -> Optional[Dict]:
    """
    Check if a target user can be modified (not an owner).
    
    Args:
        target_user: The target user dict
        action_name: The action being performed (e.g., "ban", "mute") for error message
    
    Returns:
        Error dict if target is owner and cannot be modified, None otherwise
    """
    if not target_user:
        return None
    
    target_roles = target_user.get("roles", [])
    if "owner" in target_roles:
        return {"error": f"Cannot {action_name} the server owner"}
    
    return None


def create_mod_response(emoji: str, username: str, action: str, reason: Optional[str] = None) -> Dict[str, str]:
    """
    Create a standardized moderation command response.
    
    Args:
        emoji: Emoji to prepend (e.g., "🚫", "🔇", "✅")
        username: The target username
        action: The action performed (e.g., "banned", "muted")
        reason: Optional reason for the action
    
    Returns:
        Response dict with formatted message
    """
    message = f"{emoji} **{username}** has been {action}"
    if reason:
        message += f".\n**Reason:** {reason}"
    else:
        message += "."
    
    return {"response": message}


async def disconnect_target_user(connected_clients: set, target_username: str, reason: str, server_data: dict):
    """
    Disconnect a target user from the server.
    
    Args:
        connected_clients: Set of connected WebSocket clients
        target_username: Username to disconnect
        reason: Reason for disconnection
        server_data: Server data dict
    """
    if server_data and "connected_clients" in server_data:
        await disconnect_user(
            server_data["connected_clients"],
            target_username,
            reason=reason,
            server_data=server_data
        )


def trigger_plugin_event(plugin_manager, event_name: str, ws, event_data: dict, server_data: dict):
    """
    Trigger a plugin event if plugin_manager is available.
    
    Args:
        plugin_manager: The plugin manager instance
        event_name: Name of the event to trigger
        ws: WebSocket connection
        event_data: Data to pass to the event
        server_data: Server data dict
    """
    if plugin_manager:
        plugin_manager.trigger_event(event_name, ws, event_data, server_data)


def get_user_id_from_ws(ws) -> Optional[str]:
    """
    Get the user ID from a WebSocket connection.
    
    Args:
        ws: WebSocket connection
    
    Returns:
        User ID string or None if not authenticated
    """
    return _get_ws_attr(ws, "user_id")


def get_username_from_ws(ws) -> Optional[str]:
    """
    Get the username from a WebSocket connection.
    
    Args:
        ws: WebSocket connection
    
    Returns:
        Username string or None if not available
    """
    return _get_ws_attr(ws, "username")


MOD_COMMAND_INFO = {
    "whitelistRoles": ["admin", "owner"],
    "blacklistRoles": None,
    "ephemeral": False
}


PUBLIC_COMMAND_INFO = {
    "whitelistRoles": None,
    "blacklistRoles": None,
    "ephemeral": False
}


def make_command_info(name: str, description: str, options: list, is_mod_command: bool = True) -> dict:
    """
    Create a standardized command info dict.
    
    Args:
        name: Command name
        description: Command description
        options: List of command options
        is_mod_command: Whether this is a mod-only command
    
    Returns:
        Command info dict
    """
    base = MOD_COMMAND_INFO if is_mod_command else PUBLIC_COMMAND_INFO
    return {
        "name": name,
        "description": description,
        "options": options,
        **base
    }
