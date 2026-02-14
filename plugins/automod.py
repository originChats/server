import os
import sys
import time
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import channels, users, roles
from logger import Logger


# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "automod_config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        Logger.warning("AutoMod config not found, using defaults")
        return {
            "enabled": True,
            "timeout_duration": 300,
            "blocked_words": [],
            "send_mod_message": True,
            "mod_message": "{username} was automatically timed out for violating chat rules.",
            "delete_message": True
        }

def save_config(config):
    config_path = os.path.join(os.path.dirname(__file__), "automod_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

CONFIG = load_config()
BLOCKED_WORDS = CONFIG.get("blocked_words", [])
TIMEOUT_DURATION = CONFIG.get("timeout_duration", 300)

REQUIRED_PERMISSIONS = ["owner", "admin"]


def has_permission(ws, message_data, server_data):
    """Check if user has required permissions"""
    user_id = message_data.get('user_id', getattr(ws, 'user_id', None))
    if not user_id:
        return False
    user_roles = users.get_user_roles(user_id)
    if not user_roles or not any(role in user_roles for role in REQUIRED_PERMISSIONS):
        return False
    return True


class CommandHandler:
    def __init__(self, ws, channel, server_data, username):
        self.ws = ws
        self.channel = channel
        self.server_data = server_data
        self.username = username
    
    def reply(self, message):
        send_mod_message(self.channel, message, self.server_data)
    
    def error(self, message):
        self.reply(f"❌ Error: {message}")
    
    def success(self, message):
        self.reply(f"✅ {message}")


# Command functions
def command_add(handler, args):
    """Add a word to the blocked words list"""
    if len(args) < 1:
        return handler.error("Usage: !automod add <word>")
    
    word = args[0].lower()
    if word in BLOCKED_WORDS:
        return handler.error(f"'{word}' is already in the blocked words list")
    
    CONFIG["blocked_words"].append(word)
    BLOCKED_WORDS.append(word)
    save_config(CONFIG)
    handler.success(f"Added '{word}' to blocked words")


def command_remove(handler, args):
    """Remove a word from the blocked words list"""
    if len(args) < 1:
        return handler.error("Usage: !automod remove <word>")
    
    word = args[0].lower()
    if word not in BLOCKED_WORDS:
        return handler.error(f"'{word}' is not in the blocked words list")
    
    CONFIG["blocked_words"].remove(word)
    BLOCKED_WORDS.remove(word)
    save_config(CONFIG)
    handler.success(f"Removed '{word}' from blocked words")


def command_list(handler, args):
    """List all blocked words"""
    if not BLOCKED_WORDS:
        handler.reply("No blocked words currently configured")
    else:
        words_str = "\n  • ".join(BLOCKED_WORDS)
        handler.reply(f"🚫 Blocked words ({len(BLOCKED_WORDS)}):\n  • {words_str}")


def command_clear(handler, args):
    """Clear all blocked words"""
    if not BLOCKED_WORDS:
        return handler.reply("No blocked words to clear")
    
    CONFIG["blocked_words"] = []
    BLOCKED_WORDS.clear()
    save_config(CONFIG)
    handler.success("Cleared all blocked words")


def command_status(handler, args):
    """Show automod status"""
    enabled = CONFIG.get("enabled", True)
    timeout = CONFIG.get("timeout_duration", 300)
    send_msg = CONFIG.get("send_mod_message", True)
    delete_msg = CONFIG.get("delete_message", True)
    
    status_lines = [
        f"📊 AutoMod Status",
        f"  Enabled: {'Yes' if enabled else 'No'}",
        f"  Timeout duration: {timeout}s",
        f"  Send mod message: {'Yes' if send_msg else 'No'}",
        f"  Delete violating messages: {'Yes' if delete_msg else 'No'}",
        f"  Blocked words: {len(BLOCKED_WORDS)}"
    ]
    handler.reply("\n".join(status_lines))


def command_enable(handler, args):
    """Enable automod"""
    CONFIG["enabled"] = True
    save_config(CONFIG)
    handler.success("AutoMod enabled")


def command_disable(handler, args):
    """Disable automod"""
    CONFIG["enabled"] = False
    save_config(CONFIG)
    handler.success("AutoMod disabled")


def command_timeout(handler, args):
    """Set timeout duration"""
    if len(args) < 1 or not args[0].isdigit():
        return handler.error("Usage: !automod timeout <seconds>")
    
    duration = int(args[0])
    if duration < 0:
        return handler.error("Timeout duration must be positive")
    
    CONFIG["timeout_duration"] = duration
    TIMEOUT_DURATION = duration
    save_config(CONFIG)
    handler.success(f"Timeout duration set to {duration}s")


def command_toggle_delete(handler, args):
    """Toggle whether to delete violating messages"""
    current = CONFIG.get("delete_message", True)
    CONFIG["delete_message"] = not current
    save_config(CONFIG)
    handler.success(f"Message deletion {'enabled' if not current else 'disabled'}")


COMMANDS = {
    "add": command_add,
    "remove": command_remove,
    "list": command_list,
    "clear": command_clear,
    "status": command_status,
    "enable": command_enable,
    "disable": command_disable,
    "timeout": command_timeout,
    "toggle_delete": command_toggle_delete
}


def show_help(handler, args):
    if args and args[0] in COMMANDS:
        cmd = args[0]
        func = COMMANDS[cmd]
        doc = func.__doc__ or "No help available"
        handler.reply(f"📖 {doc}")
    else:
        lines = [
            "📖 AutoMod Commands:",
            "",
            "**Word Management**",
            "  !automod add <word>",
            "  !automod remove <word>",
            "  !automod list",
            "  !automod clear",
            "",
            "**Settings**",
            "  !automod status",
            "  !automod enable",
            "  !automod disable",
            "  !automod timeout <seconds>",
            "  !automod toggle_delete",
            "",
            "💡 Use !automod help <command> for detailed help"
        ]
        handler.reply("\n".join(lines))

COMMANDS["help"] = show_help


def getInfo():
    return {
        "name": "AutoMod Plugin",
        "description": "Automatically timeout users who send messages containing blocked words. Admins/owners use !automod <command> to manage.",
        "handles": ["new_message"]
    }


def on_new_message(ws, message_data, server_data=None):
    """Handle new message events for auto-moderation"""
    if not ws or not getattr(ws, 'authenticated', False):
        return
    
    if not server_data or "rate_limiter" not in server_data:
        return
    
    user_id = message_data.get('user_id')
    username = message_data.get('username')
    content = message_data.get('content', '')
    channel = message_data.get('channel')
    message_obj = message_data.get('message', {})
    message_id = message_obj.get('id')
    
    # Handle !automod commands
    if content.startswith('!automod'):
        if not has_permission(ws, message_data, server_data):
            return
        
        parts = content[8:].strip().split()  # Remove "!automod" prefix
        if not parts:
            handler = CommandHandler(ws, channel, server_data, username)
            show_help(handler, [])
            return
        
        command = parts[0].lower()
        args = parts[1:]
        
        if command in COMMANDS:
            handler = CommandHandler(ws, channel, server_data, username)
            try:
                COMMANDS[command](handler, args)
            except Exception as e:
                Logger.error(f"Error executing automod command '{command}': {e}")
                handler.error(f"Command failed: {str(e)}")
        else:
            handler = CommandHandler(ws, channel, server_data, username)
            handler.error(f"Unknown command: {command}\nUse !automod help for available commands")
        return
    
    # Skip automod checking if disabled
    if not CONFIG.get("enabled", True):
        return
    
    # Check if message contains blocked words
    if contains_blocked_words(content):
        Logger.warning(f"AutoMod: User {username} (ID: {user_id}) sent blocked words in #{channel}")
        
        # Delete the violating message if enabled
        if message_id and CONFIG.get("delete_message", True):
            from handlers.websocket_utils import broadcast_to_all
            
            if channels.delete_channel_message(channel, message_id):
                Logger.add(f"AutoMod: Deleted message {message_id} from #{channel}")
                
                # Broadcast deletion to all clients to immediately remove it from view
                delete_msg = {
                    "cmd": "message_delete",
                    "id": message_id,
                    "channel": channel,
                    "global": True
                }
                try:
                    loop = __import__('asyncio').get_event_loop()
                    loop.create_task(broadcast_to_all(server_data["connected_clients"], delete_msg))
                except RuntimeError:
                    pass
            else:
                Logger.error(f"AutoMod: Failed to delete message {message_id}")
        
        # Apply timeout
        duration_ms = TIMEOUT_DURATION * 1000
        server_data["rate_limiter"].set_user_timeout(user_id, TIMEOUT_DURATION)
        
        # Send timeout notification to the user
        from handlers.websocket_utils import send_to_client
        try:
            loop = __import__('asyncio').get_event_loop()
            loop.create_task(send_to_client(ws, {
                "cmd": "rate_limit",
                "reason": "Automoderation: Message contains blocked words",
                "length": duration_ms
            }))
        except RuntimeError:
            pass  # No event loop running
        
        # Log the action
        Logger.add(f"AutoMod: Timed out {username} for {TIMEOUT_DURATION} seconds - blocked words")
        
        # Optionally, send a message to the channel about the timeout
        if CONFIG.get("send_mod_message", True):
            mod_msg = CONFIG.get("mod_message", "{username} was automatically timed out for violating chat rules.")
            send_mod_message(channel, mod_msg.format(username=username), server_data)
        
        # Trigger auto_moderate event for other plugins
        if "plugin_manager" in server_data:
            server_data["plugin_manager"].trigger_event("auto_moderate", ws, {
                "user_id": user_id,
                "username": username,
                "channel": channel,
                "content": content,
                "action": "timeout",
                "duration": TIMEOUT_DURATION,
                "reason": "blocked_words",
                "message_id": message_id
            }, server_data)


def contains_blocked_words(content):
    """Check if content contains any blocked words (case-insensitive)"""
    content_lower = content.lower()
    
    for word in BLOCKED_WORDS:
        if word.lower() in content_lower:
            return True
    
    return False


def send_mod_message(channel, content, server_data):
    """Send a moderation message to the channel"""
    import uuid
    
    from handlers.websocket_utils import broadcast_to_all
    import asyncio
    
    message = {
        "user": "AutoMod",
        "content": content,
        "timestamp": time.time(),
        "type": "message",
        "pinned": False,
        "id": str(uuid.uuid4())
    }
    
    # Save message to channel
    channels.save_channel_message(channel, message)
    
    # Broadcast to all users
    broadcast_msg = {
        "cmd": "message_new",
        "message": message,
        "channel": channel,
        "global": True
    }
    
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(broadcast_to_all(server_data["connected_clients"], broadcast_msg))
    except RuntimeError:
        pass
