# Welcome Plugin for OriginChats
# Sends configurable welcome messages when new users join the server

import os
import json
import time
import uuid
from db import channels, users
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import Logger

# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "welcome_channel": "general",
    "welcome_message": "Welcome {username}!",
}

def getInfo():
    """Get information about the plugin"""
    return {
        "name": "Welcome Plugin",
        "description": "Sends welcome messages when new users join the server, with configurable messages and channels.",
        "version": "1.0.0",
        "author": "OriginChats",
        "handles": [
            "user_connect"
        ]
    }

def send_message_to_channel(channel, content, server_data):
    """Send a message to a channel through the server's broadcast system"""
    import asyncio
    
    # Create a message object similar to how regular messages are created
    out_msg = {
        "user": "OriginChats",
        "content": content.strip(),
        "timestamp": time.time(),
        "type": "message",
        "pinned": False,
        "id": str(uuid.uuid4())
    }
    
    # Save to channel
    channels.save_channel_message(channel, out_msg)
    
    # Broadcast the message if we have server data
    if server_data and "connected_clients" in server_data:
        message = {"cmd": "message_new", "message": out_msg, "channel": channel, "global": True}
        # Schedule this to run in the event loop
        from handlers.websocket_utils import broadcast_to_all
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(broadcast_to_all(server_data["connected_clients"], message))
        except Exception as e:
            Logger.error(f"Welcome Plugin: Error broadcasting message: {e}")

def on_user_connect(ws, user_data, server_data=None):
    """Handle user connection event"""
    config = DEFAULT_CONFIG
    
    if not config.get("enabled", True):
        return
    
    username = user_data.get("username")
    if not username:
        return
    
    # Check if this is actually a new user (first time joining)
    user_obj = users.get_user(username)
    if user_obj:
        return
    
    # Send welcome message to channel
    welcome_channel = config.get("welcome_channel", "general")
    welcome_message = config.get("welcome_message", "Welcome {username}!")
    
    # Replace placeholders in message
    formatted_message = welcome_message.replace("{username}", f"{username}")
    
    try:
        send_message_to_channel(welcome_channel, formatted_message, server_data)
        Logger.info(f"Welcome Plugin: Sent welcome message for {username} to #{welcome_channel}")
    except Exception as e:
        Logger.error(f"Welcome Plugin: Error sending welcome message: {e}")