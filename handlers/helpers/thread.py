from db import channels, users, threads, permissions as perms
from handlers.helpers.validation import make_error as _error, require_user_id as _require_user_id
from typing import Tuple, Dict, Any, Optional


def validate_thread_access(
    ws,
    message: dict,
    match_cmd: str,
    require_view_permission: bool = True
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict]]:
    """
    Validate thread access with authentication and permission checks.
    
    Handles:
    - User authentication
    - Thread ID extraction and validation
    - Thread existence check
    - Permission validation
    
    Args:
        ws: WebSocket connection
        message: The message dict containing thread_id
        match_cmd: The command name for error reporting
        require_view_permission: Whether to check view permission
    
    Returns:
        (context, error) tuple where:
        - context: Dict with thread_data, user_id, user_roles, parent_channel, is_thread=True
        - error: Error dict if validation failed, None if success
    """
    user_id, error = _require_user_id(ws, "Authentication required")
    if error:
        return None, error
    
    if not user_id:
        return None, _error("User ID is required", match_cmd)
    
    thread_id = message.get("thread_id")
    if not thread_id:
        return None, _error("Thread ID is required", match_cmd)
    
    thread_data = threads.get_thread(thread_id)
    if not thread_data:
        return None, _error("Thread not found", match_cmd)
    
    user_roles = users.get_user_roles(user_id)
    if not user_roles:
        return None, _error("User roles not found", match_cmd)
    
    parent_channel = thread_data.get("parent_channel")
    
    if require_view_permission:
        if not channels.does_user_have_permission(parent_channel, user_roles, "view"):
            return None, _error("You do not have permission to view this thread", match_cmd)
    
    return {
        "thread_data": thread_data,
        "user_id": user_id,
        "user_roles": user_roles,
        "parent_channel": parent_channel,
        "thread_id": thread_id,
        "is_thread": True
    }, None


def validate_thread_modification(
    ws,
    message: dict,
    match_cmd: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict]]:
    """
    Validate thread modification (delete/update) with ownership checks.
    
    Handles:
    - All checks from validate_thread_access
    - Ownership verification (thread creator or manage_threads permission)
    
    Args:
        ws: WebSocket connection
        message: The message dict containing thread_id
        match_cmd: The command name for error reporting
    
    Returns:
        (context, error) tuple where:
        - context: Dict with thread_data, user_id, user_roles, parent_channel, thread_id, is_thread=True
        - error: Error dict if validation failed, None if success
    """
    ctx, error = validate_thread_access(ws, message, match_cmd, require_view_permission=False)
    if error or not ctx:
        return None, error

    thread_data = ctx["thread_data"]
    user_id = ctx["user_id"]

    is_owner = thread_data.get("created_by") == user_id
    can_manage = perms.has_permission(user_id, "manage_threads")

    if not is_owner and not can_manage:
        return None, _error("You do not have permission to modify this thread", match_cmd)

    return ctx, None


def format_thread_for_response(thread_data: dict, include_participants: bool = True) -> dict:
    """
    Format thread data for client response.
    
    Args:
        thread_data: Raw thread data from database
        include_participants: Whether to include participant usernames
    
    Returns:
        Formatted thread dict
    """
    thread_copy = thread_data.copy() if thread_data else {}
    
    if "created_by" in thread_copy:
        thread_copy["created_by"] = users.get_username_by_id(thread_copy["created_by"])
    
    if include_participants and "participants" in thread_copy:
        thread_copy["participants"] = [
            users.get_username_by_id(pid) 
            for pid in thread_copy.get("participants", [])
        ]
    
    return thread_copy
