import os
import sys
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import channels, users
from logger import Logger

REQUIRED_PERMISSIONS = ["owner"]


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "welcome_config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        Logger.warning("Welcome plugin config not found, using defaults")
        return {
            "enabled": True,
            "welcome_channel": "general",
            "welcome_message": "Welcome {username}! Thanks for joining the server.",
            "first_time_only": True
        }


def get_welcomed_users_path():
    return os.path.join(os.path.dirname(__file__), "welcomed_users.json")


def load_welcomed_users():
    """Load the set of users who have already been welcomed"""
    path = get_welcomed_users_path()
    try:
        with open(path, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()


def save_welcomed_users(welcomed_set):
    """Save the set of users who have been welcomed"""
    path = get_welcomed_users_path()
    with open(path, "w") as f:
        json.dump(list(welcomed_set), f)


def getInfo():
    return {
        "name": "Welcome Plugin",
        "description": "Sends a welcome message to users when they join the server.",
        "handles": ["user_join"]
    }


async def on_user_join(ws, message_data, server_data=None):
    """Handle user joining and send welcome message if needed"""
    try:
        config = load_config()

        if not config.get("enabled", True):
            return

        user_id = message_data.get('user_id')
        username = message_data.get('username')

        if not user_id or not username:
            Logger.warning("Welcome plugin: Missing user_id or username in user_connect event")
            return

        # Check if we should only welcome new users
        if config.get("first_time_only", True):
            welcomed_users = load_welcomed_users()
            if user_id in welcomed_users:
                Logger.info(f"Welcome plugin: User {username} already welcomed, skipping")
                return

            # Add to welcomed set
            welcomed_users.add(user_id)
            save_welcomed_users(welcomed_users)

        # Get channel for welcome message
        welcome_channel = config.get("welcome_channel", "general")
        channel_info = channels.get_channel(welcome_channel)
        if not channel_info:
            Logger.error(f"Welcome plugin: Channel '{welcome_channel}' not found")
            return

        # Format welcome message
        welcome_template = config.get("welcome_message", "Welcome {username}!")
        welcome_content = welcome_template.replace("{username}", username)

        # Create the welcome message
        import uuid
        welcome_message = {
            "user": "originChats",
            "content": welcome_content,
            "timestamp": time.time(),
            "type": "message",
            "pinned": False,
            "id": str(uuid.uuid4())
        }

        # Save to channel
        channels.save_channel_message(welcome_channel, welcome_message)

        # Broadcast to all clients in the channel
        from handlers.websocket_utils import broadcast_to_all

        if not server_data:
            Logger.warning("Welcome plugin: server_data is None, skipping broadcast")
            return

        connected_clients = server_data.get("connected_clients", [])
        if not connected_clients:
            Logger.warning("Welcome plugin: No connected clients, skipping broadcast")
            return

        broadcast_message = {
            "cmd": "message_new",
            "message": welcome_message,
            "channel": welcome_channel,
            "global": True
        }

        await broadcast_to_all(connected_clients, broadcast_message)

        Logger.success(f"Welcome message sent to {username} in #{welcome_channel}")

    except Exception as e:
        Logger.error(f"Welcome plugin error: {str(e)}")
        import traceback
        traceback.print_exc()
