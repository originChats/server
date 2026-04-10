import asyncio
import aiohttp
from logger import Logger
from typing import Callable, Set, Any, Optional

_ws_data = {}


def set_ws_data(data_dict):
    """Set the global _ws_data reference (called by server on init)"""
    global _ws_data
    _ws_data = data_dict


def _get_ws_data(ws):
    """Get ws data from _ws_data dict using ws id"""
    return _ws_data.get(id(ws), {})


def _get_ws_attr(ws, attr: str, default=None):
    """Get an attribute from ws data"""
    ws_data = _get_ws_data(ws)
    return ws_data.get(attr, default)


def _set_ws_attr(ws, attr: str, value):
    """Set an attribute in ws data"""
    ws_data_dict = _ws_data
    ws_id = id(ws)
    if ws_id not in ws_data_dict:
        ws_data_dict[ws_id] = {}
    ws_data_dict[ws_id][attr] = value


async def send_to_client(ws, message):
    """Send a message to a specific client"""
    try:
        await ws.send_json(message)
        return True
    except (aiohttp.WebSocketError, ConnectionResetError, BrokenPipeError) as e:
        Logger.warning(f"Connection closed when trying to send message: {e}")
        return False
    except Exception as e:
        Logger.error(f"Error sending message: {str(e)}")
        return False


async def heartbeat(ws, heartbeat_interval=30):
    """Send periodic pings to keep the connection alive"""
    try:
        while True:
            await asyncio.sleep(heartbeat_interval)
            if not await send_to_client(ws, {"cmd": "ping"}):
                break
    except asyncio.CancelledError:
        Logger.info("Heartbeat task cancelled")
    except Exception as e:
        Logger.error(f"Heartbeat error: {str(e)}")


async def _broadcast_to_eligible(
    connected_clients: set,
    message_func: Callable[[dict, dict], Any],
    except_client=None,
    log_prefix: str = ""
) -> Set:
    """
    Internal helper - broadcasts to clients matching predicate.
    
    Args:
        connected_clients: Set of connected WebSocket clients
        message_func: Function that takes (ws, ws_data) and returns message to send or None to skip
        except_client: Client to exclude from broadcast
        log_prefix: Prefix for log messages
    
    Returns:
        Set of disconnected clients
    """
    disconnected = set()
    clients_copy = connected_clients.copy()
    
    for ws in clients_copy:
        if ws == except_client:
            continue
        
        ws_data = _get_ws_data(ws)
        if not ws_data.get("authenticated", False):
            continue
        
        user_id = ws_data.get("user_id")
        if user_id is None:
            continue
        
        message = message_func(ws, ws_data)
        if message is None:
            continue
        
        success = await send_to_client(ws, message)
        if not success:
            disconnected.add(ws)
    
    for ws in disconnected:
        connected_clients.discard(ws)
    
    if disconnected:
        log_msg = f"Removed {len(disconnected)} disconnected clients"
        if log_prefix:
            log_msg = f"{log_prefix}: {log_msg}"
        Logger.delete(log_msg)
    
    return disconnected


async def broadcast_to_all(connected_clients, message, server_data=None):
    """Broadcast a message to all connected clients"""
    return await broadcast_to_all_except(connected_clients, message, None, server_data)


async def broadcast_to_all_except(connected_clients, message, except_client, server_data=None):
    """Broadcast a message to all connected clients except the specified client"""
    def message_func(ws, ws_data):
        return message
    
    return await _broadcast_to_eligible(connected_clients, message_func, except_client)


async def broadcast_to_channel(connected_clients, message, channel_name, server_data=None) -> set:
    """Broadcast a message to all connected clients who have access to the specified channel"""
    return await broadcast_to_channel_except(connected_clients, message, channel_name, None, server_data)


async def broadcast_to_channel_except(connected_clients, message, channel_name, except_client, server_data=None):
    """Broadcast a message to all connected clients who have access to the specified channel except the specified client"""
    from db import channels, users
    
    def message_func(ws, ws_data):
        user_id = ws_data.get("user_id")
        if not user_id:
            return None
        
        user_roles = ws_data.get("user_roles")
        if user_roles is None:
            user_data = users.get_user(user_id)
            if user_data:
                user_roles = user_data.get("roles", [])
                ws_data["user_roles"] = user_roles
            else:
                return None
        
        if channels.does_user_have_permission(channel_name, user_roles, "view"):
            return message
        return None
    
    return await _broadcast_to_eligible(connected_clients, message_func, except_client)


async def disconnect_user(connected_clients, identifier, reason="User disconnected", server_data=None):
    """Disconnect a specific user by username or user ID"""
    from db import users

    disconnected = []
    clients_copy = connected_clients.copy()

    target_user_id = identifier
    if identifier and not identifier.startswith(("USR:", "usr_")):
        lookup_user_id = users.get_id_by_username(identifier)
        if lookup_user_id:
            target_user_id = lookup_user_id

    for ws in clients_copy:
        ws_data = _get_ws_data(ws)
        ws_user_id = ws_data.get("user_id")
        ws_username = ws_data.get("username")
        if ws_username == identifier or ws_user_id == target_user_id:
            try:
                await send_to_client(ws, {"cmd": "disconnect", "reason": reason})
                await ws.close()
                disconnected.append(ws)
                Logger.delete(f"Disconnected user {identifier}: {reason}")
            except Exception as e:
                Logger.error(f"Error disconnecting user {identifier}: {str(e)}")
                disconnected.append(ws)

    for ws in disconnected:
        connected_clients.discard(ws)

    return len(disconnected)


async def broadcast_to_user(connected_clients, username, message, server_data=None):
    """Broadcast a message to all connections of a specific user"""
    from db import users

    target_user_id = users.get_id_by_username(username)
    if not target_user_id:
        target_user_id = username

    disconnected = set()
    clients_copy = connected_clients.copy()

    for ws in clients_copy:
        ws_data = _get_ws_data(ws)
        ws_user_id = ws_data.get("user_id")
        if ws_user_id == target_user_id:
            success = await send_to_client(ws, message)
            if not success:
                disconnected.add(ws)

    for ws in disconnected:
        connected_clients.discard(ws)

    return disconnected


async def broadcast_to_voice_channel_with_viewers(connected_clients, voice_channels, participant_message, viewer_message, channel_name, server_data=None):
    """Broadcast to voice channel participants (with peer_id) AND to channel viewers (without peer_id)"""
    from db import channels, users
    
    participants = voice_channels.get(channel_name, {})
    if not participants:
        return set()
    
    def message_func(ws, ws_data):
        user_id = ws_data.get("user_id")
        if not user_id:
            return None
        
        user_roles = ws_data.get("user_roles")
        if user_roles is None:
            user_data = users.get_user(user_id)
            if user_data:
                user_roles = user_data.get("roles", [])
                ws_data["user_roles"] = user_roles
            else:
                return None
        
        if not channels.does_user_have_permission(channel_name, user_roles, "view"):
            return None
        
        if user_id in participants:
            return participant_message
        return viewer_message
    
    return await _broadcast_to_eligible(
        connected_clients, 
        message_func, 
        log_prefix="voice channel broadcast"
    )
