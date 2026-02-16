import asyncio, json, websockets
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger

async def send_to_client(ws, message):
    """Send a message to a specific client"""
    try:
        await ws.send(json.dumps(message))
        return True
    except websockets.exceptions.ConnectionClosed:
        Logger.warning("Connection closed when trying to send message")
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

async def broadcast_to_all(connected_clients, message):
    """Broadcast a message to all connected clients"""
    disconnected = set()
    # Create a copy of the set to avoid "Set changed size during iteration" error
    clients_copy = connected_clients.copy()
    for ws in clients_copy:
        success = await send_to_client(ws, message)
        if not success:
            disconnected.add(ws)
    
    # Clean up disconnected clients
    for ws in disconnected:
        connected_clients.discard(ws)  # Use discard instead of remove to avoid KeyError
    
    if disconnected:
        Logger.delete(f"Removed {len(disconnected)} disconnected clients")
    
    return disconnected

async def broadcast_to_channel(connected_clients, message, channel_name):
    """Broadcast a message to all connected clients who have access to the specified channel"""
    from db import channels
    
    disconnected = set()
    sent_count = 0
    
    clients_copy = connected_clients.copy()
    
    for ws in clients_copy:
        if not getattr(ws, 'authenticated', False):
            continue
            
        user_id = getattr(ws, 'user_id', None)
        if not user_id:
            continue
        
        user_roles = getattr(ws, 'user_roles', None)
        if user_roles is None:
            from db import users
            user_data = users.get_user(user_id)
            if user_data:
                user_roles = user_data.get("roles", [])
                ws.user_roles = user_roles
            else:
                continue
        
        if channels.does_user_have_permission(channel_name, user_roles, "view"):
            success = await send_to_client(ws, message)
            if not success:
                disconnected.add(ws)
            else:
                sent_count += 1
    
    for ws in disconnected:
        connected_clients.discard(ws)
    
    if disconnected:
        Logger.delete(f"Removed {len(disconnected)} disconnected clients")
    
    return disconnected

async def disconnect_user(connected_clients, identifier, reason="User disconnected"):
    """Disconnect a specific user by username or user ID"""
    from db import users
    
    disconnected = []
    clients_copy = connected_clients.copy()
    
    # Try to get user ID if username is provided
    target_user_id = identifier
    if identifier and not identifier.startswith(("USR:", "usr_")):  # Likely a username
        lookup_user_id = users.get_id_by_username(identifier)
        if lookup_user_id:
            target_user_id = lookup_user_id
    
    for ws in clients_copy:
        ws_user_id = getattr(ws, 'user_id', None)
        if hasattr(ws, 'username') and (ws.username == identifier or ws_user_id == target_user_id):
            try:
                await send_to_client(ws, {"cmd": "disconnect", "reason": reason})
                await ws.close()
                disconnected.append(ws)
                Logger.delete(f"Disconnected user {identifier}: {reason}")
            except Exception as e:
                Logger.error(f"Error disconnecting user {identifier}: {str(e)}")
                disconnected.append(ws)
    
    # Clean up disconnected clients
    for ws in disconnected:
        connected_clients.discard(ws)
    
    return len(disconnected)

async def broadcast_to_voice_channel(connected_clients, voice_channels, message, channel_name):
    """Broadcast a message to all connected clients who are in a specific voice channel"""
    disconnected = set()
    sent_count = 0
    
    # Get participants in this voice channel
    participants = voice_channels.get(channel_name, {})
    if not participants:
        return disconnected
    
    # Create a copy of the set to avoid "Set changed size during iteration" error
    clients_copy = connected_clients.copy()
    
    for ws in clients_copy:
        # Only send to authenticated users
        if not getattr(ws, 'authenticated', False):
            continue
            
        user_id = getattr(ws, 'user_id', None)
        if not user_id:
            continue
        
        # Check if user is in this voice channel
        if user_id in participants:
            success = await send_to_client(ws, message)
            if not success:
                disconnected.add(ws)
            else:
                sent_count += 1
    
    # Clean up disconnected clients
    for ws in disconnected:
        connected_clients.discard(ws)
    
    if disconnected:
        Logger.delete(f"Removed {len(disconnected)} disconnected clients from voice channel broadcast")
    
    return disconnected

async def broadcast_to_voice_channel_with_viewers(connected_clients, voice_channels, participant_message, viewer_message, channel_name):
    """Broadcast to voice channel participants (with peer_id) AND to channel viewers (without peer_id)"""
    from db import channels
    
    disconnected = set()
    sent_count = 0
    
    participants = voice_channels.get(channel_name, {})
    if not participants:
        return disconnected
    
    clients_copy = connected_clients.copy()
    
    for ws in clients_copy:
        if not getattr(ws, 'authenticated', False):
            continue
            
        user_id = getattr(ws, 'user_id', None)
        if not user_id:
            continue
        
        user_roles = getattr(ws, 'user_roles', None)
        if user_roles is None:
            from db import users
            user_data = users.get_user(user_id)
            if user_data:
                user_roles = user_data.get("roles", [])
                ws.user_roles = user_roles
            else:
                continue
        
        if not channels.does_user_have_permission(channel_name, user_roles, "view"):
            continue
        
        if user_id in participants:
            success = await send_to_client(ws, participant_message)
        else:
            success = await send_to_client(ws, viewer_message)
        
        if not success:
            disconnected.add(ws)
        else:
            sent_count += 1
    
    for ws in disconnected:
        connected_clients.discard(ws)
    
    if disconnected:
        Logger.delete(f"Removed {len(disconnected)} disconnected clients from voice channel broadcast")
    
    return disconnected
